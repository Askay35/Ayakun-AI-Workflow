import uuid
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.billing import BillingAudit, Payment, Plan, Wallet, WalletLedger
from models.user import User
from models.workflow import NodeRun, Workflow, WorkflowRun, WorkflowVersion
from schemas.admin import (
    AdminLedgerEntryResponse,
    AdminPage,
    AdminPaymentResponse,
    AdminPaymentUpdate,
    AdminRunResponse,
    AdminRunUpdate,
    AdminUserResponse,
    AdminUserUpdate,
    AdminWorkflowResponse,
    AdminWorkflowUpdate,
)
from services.billing import BillingService


def _integrity_message(exc: IntegrityError, *, deleting: bool, entity: str) -> str:
    orig = getattr(exc, "orig", None)
    name = type(orig).__name__ if orig is not None else ""
    text = str(orig or exc).lower()
    if deleting or "foreignkey" in name.lower() or "foreign key" in text:
        return f"Нельзя удалить {entity}: на запись ссылаются другие данные"
    if "email" in text or "users_email" in text:
        return "Этот email уже занят"
    if "chat_id" in text:
        return "Этот Telegram chat_id уже занят"
    if "unique" in name.lower() or "unique" in text:
        return "Конфликт данных: значение уже используется"
    return f"Не удалось сохранить {entity}"


def _plan_credits(plan: Plan | None) -> Decimal | None:
    if not plan:
        return None
    return Decimal(str((plan.limits or {}).get("included_credits", 0)))


def _nodes_count(workflow: Workflow) -> int:
    graph = workflow.draft_graph or {}
    nodes = graph.get("nodes") if isinstance(graph, dict) else None
    return len(nodes) if isinstance(nodes, list) else 0


class AdminRecordsService:
    def __init__(self, db: AsyncSession, billing: BillingService):
        self.db = db
        self.billing = billing

    async def _seen(self, request_id: str) -> bool:
        return bool(await self.db.scalar(select(BillingAudit.id).where(BillingAudit.request_id == request_id)))

    def _queue_audit(
        self,
        *,
        actor: str,
        action: str,
        entity_type: str,
        entity_id: str,
        before: dict,
        after: dict,
        request_id: str,
    ) -> None:
        self.db.add(BillingAudit(
            actor=actor,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before=before,
            after=after,
            request_id=request_id,
        ))

    async def _commit(self, *, deleting: bool, entity: str) -> None:
        try:
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            raise HTTPException(409, _integrity_message(exc, deleting=deleting, entity=entity)) from exc

    def _user_payload(self, user: User, wallet: Wallet | None, *, ledger: list[WalletLedger] | None = None) -> AdminUserResponse:
        return AdminUserResponse(
            id=user.id,
            name=user.name,
            email=user.email,
            chat_id=user.chat_id,
            email_verified=user.email_verified,
            is_active=user.is_active,
            balance=wallet.balance if wallet else Decimal("0"),
            reserved=wallet.reserved if wallet else Decimal("0"),
            identities=user.identities,
            ledger=[
                AdminLedgerEntryResponse(
                    id=item.id,
                    kind=item.kind,
                    amount=item.amount,
                    reference=item.reference,
                    metadata=item.metadata_ or {},
                    created_at=item.created_at,
                )
                for item in (ledger or [])
            ],
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    def _payment_payload(self, payment: Payment) -> AdminPaymentResponse:
        user = payment.user
        plan = payment.plan
        return AdminPaymentResponse(
            id=payment.id,
            user_id=payment.user_id,
            user_name=user.name if user else None,
            user_email=user.email if user else None,
            plan_id=payment.plan_id,
            plan_name=plan.name if plan else None,
            plan_code=plan.code if plan else None,
            credits=_plan_credits(plan),
            provider=payment.provider,
            provider_payment_id=payment.provider_payment_id,
            amount=payment.amount,
            status=payment.status,
            created_at=payment.created_at,
            updated_at=payment.updated_at,
        )

    def _workflow_payload(self, workflow: Workflow, owner: User | None = None) -> AdminWorkflowResponse:
        user = owner or workflow.user
        return AdminWorkflowResponse(
            id=workflow.id,
            owner_id=workflow.owner_id,
            owner_name=user.name if user else None,
            owner_email=user.email if user else None,
            name=workflow.name,
            description=workflow.description,
            status=workflow.status,
            schedule_cron=workflow.schedule_cron,
            schedule_timezone=workflow.schedule_timezone,
            next_run_at=workflow.next_run_at,
            estimated_run_cost=workflow.estimated_run_cost,
            nodes_count=_nodes_count(workflow),
            created_at=workflow.created_at,
            updated_at=workflow.updated_at,
        )

    def _run_payload(self, run: WorkflowRun, owner: User | None = None, workflow: Workflow | None = None) -> AdminRunResponse:
        linked_workflow = workflow or run.workflow
        return AdminRunResponse(
            id=run.id,
            workflow_id=run.workflow_id,
            workflow_name=linked_workflow.name if linked_workflow else None,
            workflow_version_id=run.workflow_version_id,
            owner_id=run.owner_id,
            owner_name=owner.name if owner else None,
            owner_email=owner.email if owner else None,
            status=run.status,
            error=run.error,
            cost=run.cost,
            cancel_requested=run.cancel_requested,
            started_at=run.started_at,
            finished_at=run.finished_at,
            created_at=run.created_at,
        )

    async def _get_user(self, user_id: int) -> User:
        user = await self.db.get(User, user_id)
        if not user:
            raise HTTPException(404, "Пользователь не найден")
        return user

    async def _user_with_wallet(self, user_id: int, *, with_ledger: bool = False) -> AdminUserResponse:
        user = await self._get_user(user_id)
        wallet = await self.db.get(Wallet, user_id)
        ledger = None
        if with_ledger:
            ledger = list(await self.db.scalars(
                select(WalletLedger)
                .where(WalletLedger.user_id == user_id)
                .order_by(WalletLedger.created_at.desc())
                .limit(30)
            ))
        return self._user_payload(user, wallet, ledger=ledger)

    async def list_users(
        self,
        *,
        q: str | None,
        is_active: bool | None,
        page: int,
        page_size: int,
    ) -> AdminPage[AdminUserResponse]:
        filters = []
        if q:
            term = q.strip()
            clauses = [User.name.ilike(f"%{term}%"), User.email.ilike(f"%{term}%")]
            if term.isdigit():
                clauses.append(User.id == int(term))
                clauses.append(User.chat_id == int(term))
            filters.append(or_(*clauses))
        if is_active is not None:
            filters.append(User.is_active.is_(is_active))
        total = await self.db.scalar(select(func.count(User.id)).where(*filters)) or 0
        rows = await self.db.execute(
            select(User, Wallet)
            .outerjoin(Wallet, Wallet.user_id == User.id)
            .where(*filters)
            .order_by(User.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = [self._user_payload(user, wallet) for user, wallet in rows.all()]
        return AdminPage(items=items, total=int(total), page=page, page_size=page_size)

    async def get_user(self, user_id: int) -> AdminUserResponse:
        return await self._user_with_wallet(user_id, with_ledger=True)

    async def update_user(self, user_id: int, data: AdminUserUpdate, actor: str) -> AdminUserResponse:
        if await self._seen(data.request_id):
            return await self._user_with_wallet(user_id, with_ledger=True)
        user = await self.db.get(User, user_id, with_for_update=True)
        if not user:
            raise HTTPException(404, "Пользователь не найден")
        before = self._user_payload(user, await self.db.get(Wallet, user_id)).model_dump(mode="json")
        if data.name is not None:
            user.name = data.name.strip()
        if "email" in data.model_fields_set:
            user.email = data.email
        if "chat_id" in data.model_fields_set:
            user.chat_id = data.chat_id
        if data.email_verified is not None:
            user.email_verified = data.email_verified
        if data.is_active is not None:
            user.is_active = data.is_active
        try:
            await self.db.flush()
        except IntegrityError as exc:
            await self.db.rollback()
            raise HTTPException(409, _integrity_message(exc, deleting=False, entity="пользователя")) from exc
        if "balance" in data.model_fields_set and data.balance is not None:
            await self.billing.set_balance(
                user,
                data.balance,
                f"admin-balance:{data.request_id}",
                actor=actor,
                note=data.note,
            )
        after = (await self._user_with_wallet(user_id)).model_dump(mode="json")
        self._queue_audit(
            actor=actor,
            action="update",
            entity_type="user",
            entity_id=str(user_id),
            before=before,
            after=after,
            request_id=data.request_id,
        )
        await self._commit(deleting=False, entity="пользователя")
        return await self._user_with_wallet(user_id, with_ledger=True)

    async def delete_user(self, user_id: int, actor: str, request_id: str) -> None:
        if await self._seen(request_id):
            return
        user = await self._get_user(user_id)
        before = (await self._user_with_wallet(user_id)).model_dump(mode="json")
        workflows = list(await self.db.scalars(select(Workflow).where(Workflow.owner_id == user_id)))
        for workflow in workflows:
            await self._delete_workflow_graph(workflow.id)
        await self.db.delete(user)
        self._queue_audit(
            actor=actor,
            action="delete",
            entity_type="user",
            entity_id=str(user_id),
            before=before,
            after={},
            request_id=request_id,
        )
        await self._commit(deleting=True, entity="пользователя")

    async def list_payments(
        self,
        *,
        q: str | None,
        status: str | None,
        user_id: int | None,
        page: int,
        page_size: int,
    ) -> AdminPage[AdminPaymentResponse]:
        filters = []
        if user_id is not None:
            filters.append(Payment.user_id == user_id)
        if status:
            filters.append(Payment.status == status)
        if q:
            term = q.strip()
            clauses = [
                User.name.ilike(f"%{term}%"),
                User.email.ilike(f"%{term}%"),
                Payment.provider.ilike(f"%{term}%"),
                Payment.provider_payment_id.ilike(f"%{term}%"),
            ]
            parsed = _parse_uuid(term)
            if parsed:
                clauses.append(Payment.id == parsed)
            if term.isdigit():
                clauses.append(Payment.user_id == int(term))
            filters.append(or_(*clauses))
        total = await self.db.scalar(
            select(func.count(Payment.id)).outerjoin(User, User.id == Payment.user_id).where(*filters)
        ) or 0
        items = list(await self.db.scalars(
            select(Payment)
            .outerjoin(User, User.id == Payment.user_id)
            .where(*filters)
            .options(selectinload(Payment.user), selectinload(Payment.plan))
            .order_by(Payment.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ))
        return AdminPage(
            items=[self._payment_payload(item) for item in items],
            total=int(total),
            page=page,
            page_size=page_size,
        )

    async def get_payment(self, payment_id: uuid.UUID) -> AdminPaymentResponse:
        payment = await self.db.get(Payment, payment_id, options=(selectinload(Payment.user), selectinload(Payment.plan)))
        if not payment:
            raise HTTPException(404, "Платёж не найден")
        return self._payment_payload(payment)

    async def update_payment(self, payment_id: uuid.UUID, data: AdminPaymentUpdate, actor: str) -> AdminPaymentResponse:
        if await self._seen(data.request_id):
            return await self.get_payment(payment_id)
        payment = await self.db.get(
            Payment,
            payment_id,
            with_for_update=True,
            options=(selectinload(Payment.user), selectinload(Payment.plan)),
        )
        if not payment:
            raise HTTPException(404, "Платёж не найден")
        before = self._payment_payload(payment).model_dump(mode="json")
        if data.status is not None:
            payment.status = data.status
        if data.amount is not None:
            payment.amount = data.amount
        if "plan_id" in data.model_fields_set:
            if data.plan_id is not None and not await self.db.get(Plan, data.plan_id):
                raise HTTPException(404, "Тариф не найден")
            payment.plan_id = data.plan_id
        await self.db.flush()
        await self.db.refresh(payment, attribute_names=["plan", "user"])
        after = self._payment_payload(payment).model_dump(mode="json")
        self._queue_audit(
            actor=actor,
            action="update",
            entity_type="payment",
            entity_id=str(payment_id),
            before=before,
            after=after,
            request_id=data.request_id,
        )
        await self._commit(deleting=False, entity="платёж")
        return await self.get_payment(payment_id)

    async def delete_payment(self, payment_id: uuid.UUID, actor: str, request_id: str) -> None:
        if await self._seen(request_id):
            return
        payment = await self.db.get(Payment, payment_id, options=(selectinload(Payment.user), selectinload(Payment.plan)))
        if not payment:
            raise HTTPException(404, "Платёж не найден")
        before = self._payment_payload(payment).model_dump(mode="json")
        await self.db.delete(payment)
        self._queue_audit(
            actor=actor,
            action="delete",
            entity_type="payment",
            entity_id=str(payment_id),
            before=before,
            after={},
            request_id=request_id,
        )
        await self._commit(deleting=True, entity="платёж")

    async def list_workflows(
        self,
        *,
        q: str | None,
        status: str | None,
        user_id: int | None,
        page: int,
        page_size: int,
    ) -> AdminPage[AdminWorkflowResponse]:
        filters = []
        if user_id is not None:
            filters.append(Workflow.owner_id == user_id)
        if status:
            filters.append(Workflow.status == status)
        if q:
            term = q.strip()
            clauses = [Workflow.name.ilike(f"%{term}%"), User.name.ilike(f"%{term}%"), User.email.ilike(f"%{term}%")]
            parsed = _parse_uuid(term)
            if parsed:
                clauses.append(Workflow.id == parsed)
            if term.isdigit():
                clauses.append(Workflow.owner_id == int(term))
            filters.append(or_(*clauses))
        total = await self.db.scalar(
            select(func.count(Workflow.id)).outerjoin(User, User.id == Workflow.owner_id).where(*filters)
        ) or 0
        rows = await self.db.execute(
            select(Workflow, User)
            .outerjoin(User, User.id == Workflow.owner_id)
            .where(*filters)
            .order_by(Workflow.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = [self._workflow_payload(workflow, owner) for workflow, owner in rows.all()]
        return AdminPage(items=items, total=int(total), page=page, page_size=page_size)

    async def get_workflow(self, workflow_id: uuid.UUID) -> AdminWorkflowResponse:
        row = await self.db.execute(
            select(Workflow, User)
            .outerjoin(User, User.id == Workflow.owner_id)
            .where(Workflow.id == workflow_id)
        )
        result = row.first()
        if not result:
            raise HTTPException(404, "Цепочка не найдена")
        workflow, owner = result
        return self._workflow_payload(workflow, owner)

    async def update_workflow(self, workflow_id: uuid.UUID, data: AdminWorkflowUpdate, actor: str) -> AdminWorkflowResponse:
        if await self._seen(data.request_id):
            return await self.get_workflow(workflow_id)
        workflow = await self.db.get(Workflow, workflow_id, with_for_update=True)
        if not workflow:
            raise HTTPException(404, "Цепочка не найдена")
        owner = await self.db.get(User, workflow.owner_id)
        before = self._workflow_payload(workflow, owner).model_dump(mode="json")
        if data.name is not None:
            workflow.name = data.name.strip()
        if "description" in data.model_fields_set:
            workflow.description = data.description
        if data.status is not None:
            workflow.status = data.status
        if "schedule_cron" in data.model_fields_set:
            workflow.schedule_cron = data.schedule_cron
        if data.schedule_timezone is not None:
            workflow.schedule_timezone = data.schedule_timezone
        after = self._workflow_payload(workflow, owner).model_dump(mode="json")
        self._queue_audit(
            actor=actor,
            action="update",
            entity_type="workflow",
            entity_id=str(workflow_id),
            before=before,
            after=after,
            request_id=data.request_id,
        )
        await self._commit(deleting=False, entity="цепочку")
        return await self.get_workflow(workflow_id)

    async def delete_workflow(self, workflow_id: uuid.UUID, actor: str, request_id: str) -> None:
        if await self._seen(request_id):
            return
        payload = await self.get_workflow(workflow_id)
        await self._delete_workflow_graph(workflow_id)
        self._queue_audit(
            actor=actor,
            action="delete",
            entity_type="workflow",
            entity_id=str(workflow_id),
            before=payload.model_dump(mode="json"),
            after={},
            request_id=request_id,
        )
        await self._commit(deleting=True, entity="цепочку")

    async def _delete_workflow_graph(self, workflow_id: uuid.UUID) -> None:
        run_ids = list(await self.db.scalars(select(WorkflowRun.id).where(WorkflowRun.workflow_id == workflow_id)))
        if run_ids:
            await self.db.execute(delete(NodeRun).where(NodeRun.workflow_run_id.in_(run_ids)))
            await self.db.execute(delete(WorkflowRun).where(WorkflowRun.id.in_(run_ids)))
        await self.db.execute(delete(WorkflowVersion).where(WorkflowVersion.workflow_id == workflow_id))
        workflow = await self.db.get(Workflow, workflow_id)
        if workflow:
            await self.db.delete(workflow)

    async def list_runs(
        self,
        *,
        q: str | None,
        status: str | None,
        user_id: int | None,
        page: int,
        page_size: int,
    ) -> AdminPage[AdminRunResponse]:
        filters = []
        if user_id is not None:
            filters.append(WorkflowRun.owner_id == user_id)
        if status:
            filters.append(WorkflowRun.status == status)
        if q:
            term = q.strip()
            clauses = [
                Workflow.name.ilike(f"%{term}%"),
                User.name.ilike(f"%{term}%"),
                User.email.ilike(f"%{term}%"),
                WorkflowRun.error.ilike(f"%{term}%"),
            ]
            parsed = _parse_uuid(term)
            if parsed:
                clauses.append(WorkflowRun.id == parsed)
                clauses.append(WorkflowRun.workflow_id == parsed)
            if term.isdigit():
                clauses.append(WorkflowRun.owner_id == int(term))
            filters.append(or_(*clauses))
        total = await self.db.scalar(
            select(func.count(WorkflowRun.id))
            .outerjoin(User, User.id == WorkflowRun.owner_id)
            .outerjoin(Workflow, Workflow.id == WorkflowRun.workflow_id)
            .where(*filters)
        ) or 0
        rows = await self.db.execute(
            select(WorkflowRun, User, Workflow)
            .outerjoin(User, User.id == WorkflowRun.owner_id)
            .outerjoin(Workflow, Workflow.id == WorkflowRun.workflow_id)
            .where(*filters)
            .order_by(WorkflowRun.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = [self._run_payload(run, owner, workflow) for run, owner, workflow in rows.all()]
        return AdminPage(items=items, total=int(total), page=page, page_size=page_size)

    async def get_run(self, run_id: uuid.UUID) -> AdminRunResponse:
        row = await self.db.execute(
            select(WorkflowRun, User, Workflow)
            .outerjoin(User, User.id == WorkflowRun.owner_id)
            .outerjoin(Workflow, Workflow.id == WorkflowRun.workflow_id)
            .where(WorkflowRun.id == run_id)
        )
        result = row.first()
        if not result:
            raise HTTPException(404, "Запуск не найден")
        run, owner, workflow = result
        return self._run_payload(run, owner, workflow)

    async def update_run(self, run_id: uuid.UUID, data: AdminRunUpdate, actor: str) -> AdminRunResponse:
        if await self._seen(data.request_id):
            return await self.get_run(run_id)
        run = await self.db.get(WorkflowRun, run_id, with_for_update=True)
        if not run:
            raise HTTPException(404, "Запуск не найден")
        owner = await self.db.get(User, run.owner_id)
        workflow = await self.db.get(Workflow, run.workflow_id)
        before = self._run_payload(run, owner, workflow).model_dump(mode="json")
        if data.status is not None:
            run.status = data.status
        if "error" in data.model_fields_set:
            run.error = data.error
        if data.cancel_requested is not None:
            run.cancel_requested = data.cancel_requested
        after = self._run_payload(run, owner, workflow).model_dump(mode="json")
        self._queue_audit(
            actor=actor,
            action="update",
            entity_type="workflow_run",
            entity_id=str(run_id),
            before=before,
            after=after,
            request_id=data.request_id,
        )
        await self._commit(deleting=False, entity="запуск")
        return await self.get_run(run_id)

    async def delete_run(self, run_id: uuid.UUID, actor: str, request_id: str) -> None:
        if await self._seen(request_id):
            return
        payload = await self.get_run(run_id)
        await self.db.execute(delete(NodeRun).where(NodeRun.workflow_run_id == run_id))
        run = await self.db.get(WorkflowRun, run_id)
        if run:
            await self.db.delete(run)
        self._queue_audit(
            actor=actor,
            action="delete",
            entity_type="workflow_run",
            entity_id=str(run_id),
            before=payload.model_dump(mode="json"),
            after={},
            request_id=request_id,
        )
        await self._commit(deleting=True, entity="запуск")


def _parse_uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(value)
    except ValueError:
        return None
