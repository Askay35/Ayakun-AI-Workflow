<template>
  <div class="shot-story">
    <figure class="shot-card is-dark reveal">
      <img src="/images/workflow2.png" :alt="t('landing.shots.chainAlt')" width="1920" height="908" loading="lazy" />
      <figcaption>
        <span class="shot-step">{{ t('landing.shots.chainStep') }}</span>
        <strong>{{ t('landing.shots.chainTitle') }}</strong>
        <p>{{ t('landing.shots.chainText') }}</p>
      </figcaption>
    </figure>

    <div class="shot-split">
      <figure class="shot-card is-light reveal" style="animation-delay: 80ms">
        <img src="/images/workflow_run.png" class="step-2-img" :alt="t('landing.shots.runAlt')" width="1600" height="900" loading="lazy" />
        <figcaption>
          <span class="shot-step">{{ t('landing.shots.runStep') }}</span>
          <strong>{{ t('landing.shots.runTitle') }}</strong>
          <p>{{ t('landing.shots.runText') }}</p>
        </figcaption>
      </figure>
      <figure class="shot-card is-phone reveal" style="animation-delay: 140ms">
        <img src="/images/tg.png" :alt="t('landing.shots.tgAlt')" width="720" height="1280" loading="lazy" />
        <figcaption>
          <span class="shot-step">{{ t('landing.shots.tgStep') }}</span>
          <strong>{{ t('landing.shots.tgTitle') }}</strong>
          <p>{{ t('landing.shots.tgText') }}</p>
        </figcaption>
      </figure>
    </div>

    <figure class="shot-card is-dark reveal" style="animation-delay: 180ms">
      <img src="/images/workflow.png" :alt="t('landing.shots.moreAlt')" width="1920" height="908" loading="lazy" />
      <figcaption>
        <span class="shot-step">{{ t('landing.shots.moreStep') }}</span>
        <strong>{{ t('landing.shots.moreTitle') }}</strong>
        <p>{{ t('landing.shots.moreText') }}</p>
      </figcaption>
    </figure>
  </div>
</template>
<script setup lang="ts">
const { t } = useI18n()
</script>
<style scoped>
.step-2-img {
  width: 100%;
  object-fit: cover;
}
</style>
