export default defineAppConfig({
  ui: {
    colors: {
      primary: 'violet',
      neutral: 'slate'
    },
    button: {
      slots: {
        base: 'rounded-xl font-bold inline-flex items-center cursor-pointer disabled:cursor-not-allowed disabled:opacity-60 transition-all duration-200'
      },
      variants: {
        size: {
          xs: { base: 'px-2.5 py-1.5 text-xs gap-1' },
          sm: { base: 'px-3 py-2 text-xs gap-1.5' },
          md: { base: 'px-4 py-2.5 text-sm gap-2' },
          lg: { base: 'px-5 py-3 text-sm gap-2' },
          xl: { base: 'px-6 py-3.5 text-base gap-2.5' }
        }
      }
    },
    formField: {
      slots: {
        root: 'w-full',
        label: 'block mb-2 text-[13px] font-bold tracking-[-0.01em] text-[#22284a]',
        container: 'mt-0',
        description: 'mt-1.5 text-xs text-[#6b7090]',
        error: 'mt-1.5 text-xs font-semibold text-error',
        help: 'mt-1.5 text-xs text-[#6b7090]'
      },
      defaultVariants: {
        size: 'lg'
      }
    },
    input: {
      slots: {
        root: 'relative inline-flex w-full items-center',
        base: [
          'w-full rounded-2xl border-0 appearance-none font-semibold tracking-[-0.01em]',
          'placeholder:text-[#9a9fba] placeholder:font-medium',
          'disabled:cursor-not-allowed disabled:opacity-60',
          'transition-[box-shadow,background-color,color] duration-200'
        ],
        leading: 'absolute inset-y-0 start-0 flex items-center',
        leadingIcon: 'shrink-0 text-[#8a8fa8]',
        trailing: 'absolute inset-y-0 end-0 flex items-center',
        trailingIcon: 'shrink-0 text-[#8a8fa8]'
      },
      variants: {
        size: {
          xs: {
            base: 'px-3 py-2 text-sm gap-1',
            leading: 'ps-3',
            trailing: 'pe-3',
            leadingIcon: 'size-4',
            trailingIcon: 'size-4'
          },
          sm: {
            base: 'px-3.5 py-2.5 text-sm gap-1.5',
            leading: 'ps-3.5',
            trailing: 'pe-3.5',
            leadingIcon: 'size-4',
            trailingIcon: 'size-4'
          },
          md: {
            base: 'px-4 py-3 text-[15px] gap-2',
            leading: 'ps-4',
            trailing: 'pe-4',
            leadingIcon: 'size-5',
            trailingIcon: 'size-5'
          },
          lg: {
            base: 'px-[18px] py-3.5 text-[15px] gap-2',
            leading: 'ps-4',
            trailing: 'pe-4',
            leadingIcon: 'size-5',
            trailingIcon: 'size-5'
          },
          xl: {
            base: 'px-5 py-4 text-base gap-2',
            leading: 'ps-5',
            trailing: 'pe-5',
            leadingIcon: 'size-5',
            trailingIcon: 'size-5'
          }
        },
        variant: {
          outline: 'text-[#0f1330] bg-[#f6f7fd] ring-1 ring-inset ring-[#e2e5f1] hover:bg-white hover:ring-[#c9cee3] focus:bg-white focus-visible:ring-2 focus-visible:ring-[#6d4aff]',
          soft: 'text-[#0f1330] bg-[#eff0f8] hover:bg-[#e6e8f5] focus:bg-white focus-visible:ring-2 focus-visible:ring-[#6d4aff]',
          subtle: 'text-[#0f1330] bg-[#f6f7fd] ring-1 ring-inset ring-[#e6e8f2] hover:bg-white focus:bg-white focus-visible:ring-2 focus-visible:ring-[#6d4aff]',
          ghost: 'text-[#0f1330] bg-transparent hover:bg-[#eff0f8] focus:bg-[#f6f7fd]',
          none: 'text-[#0f1330] bg-transparent focus:outline-none'
        }
      },
      compoundVariants: [
        {
          leading: true,
          size: 'md',
          class: 'ps-11'
        },
        {
          leading: true,
          size: 'lg',
          class: 'ps-12'
        },
        {
          leading: true,
          size: 'xl',
          class: 'ps-12'
        },
        {
          trailing: true,
          size: 'md',
          class: 'pe-11'
        },
        {
          trailing: true,
          size: 'lg',
          class: 'pe-12'
        },
        {
          trailing: true,
          size: 'xl',
          class: 'pe-12'
        }
      ],
      defaultVariants: {
        size: 'lg',
        color: 'primary',
        variant: 'outline'
      }
    },
    textarea: {
      slots: {
        root: 'relative inline-flex w-full items-center',
        base: [
          'w-full rounded-2xl border-0 appearance-none font-semibold tracking-[-0.01em] leading-6',
          'placeholder:text-[#9a9fba] placeholder:font-medium',
          'disabled:cursor-not-allowed disabled:opacity-60',
          'transition-[box-shadow,background-color,color] duration-200'
        ]
      },
      variants: {
        size: {
          md: { base: 'px-4 py-3 text-[15px]' },
          lg: { base: 'px-[18px] py-3.5 text-[15px]' },
          xl: { base: 'px-5 py-4 text-base' }
        },
        variant: {
          outline: 'text-[#0f1330] bg-[#f6f7fd] ring-1 ring-inset ring-[#e2e5f1] hover:bg-white hover:ring-[#c9cee3] focus:bg-white focus-visible:ring-2 focus-visible:ring-[#6d4aff]',
          soft: 'text-[#0f1330] bg-[#eff0f8] hover:bg-[#e6e8f5] focus:bg-white focus-visible:ring-2 focus-visible:ring-[#6d4aff]',
          subtle: 'text-[#0f1330] bg-[#f6f7fd] ring-1 ring-inset ring-[#e6e8f2] hover:bg-white focus:bg-white focus-visible:ring-2 focus-visible:ring-[#6d4aff]',
          ghost: 'text-[#0f1330] bg-transparent hover:bg-[#eff0f8] focus:bg-[#f6f7fd]',
          none: 'text-[#0f1330] bg-transparent focus:outline-none'
        }
      },
      defaultVariants: {
        size: 'lg',
        color: 'primary',
        variant: 'outline'
      }
    },
    select: {
      slots: {
        base: [
          'relative group rounded-2xl inline-flex w-full items-center font-semibold tracking-[-0.01em]',
          'disabled:cursor-not-allowed disabled:opacity-60',
          'transition-[box-shadow,background-color,color] duration-200'
        ],
        content: 'min-w-(--reka-select-trigger-width) w-max max-w-[min(28rem,calc(100vw-2rem))] rounded-xl ring ring-[#e6e8f2] shadow-xl',
        item: 'rounded-lg'
      },
      variants: {
        size: {
          md: { base: 'px-4 py-3 text-[15px]' },
          lg: { base: 'px-[18px] py-3.5 text-[15px]' },
          xl: { base: 'px-5 py-4 text-base' }
        },
        variant: {
          outline: 'text-[#0f1330] bg-[#f6f7fd] ring-1 ring-inset ring-[#e2e5f1] hover:bg-white hover:ring-[#c9cee3] focus:bg-white data-[state=open]:bg-white data-[state=open]:ring-2 data-[state=open]:ring-[#6d4aff]',
          soft: 'text-[#0f1330] bg-[#eff0f8] hover:bg-[#e6e8f5] focus:bg-white',
          subtle: 'text-[#0f1330] bg-[#f6f7fd] ring-1 ring-inset ring-[#e6e8f2] hover:bg-white focus:bg-white',
          ghost: 'text-[#0f1330] bg-transparent hover:bg-[#eff0f8] focus:bg-[#f6f7fd]',
          none: 'text-[#0f1330] bg-transparent focus:outline-none'
        }
      },
      defaultVariants: {
        size: 'lg',
        color: 'primary',
        variant: 'outline'
      }
    }
  }
})
