import { Directive, computed, input } from '@angular/core';
import { cva, type VariantProps } from 'class-variance-authority';
import type { ClassValue } from 'clsx';

import { ClassMerge } from './class-merge';
import { cn } from './cn';

@Directive({ selector: 'input[uiInput], select[uiInput]', standalone: true })
export class UiInput extends ClassMerge {
  protected readonly base =
    'flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-base shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 md:text-sm';
}

@Directive({ selector: 'textarea[uiTextarea]', standalone: true })
export class UiTextarea extends ClassMerge {
  protected readonly base =
    'flex min-h-[60px] w-full rounded-md border border-input bg-transparent px-3 py-2 text-base shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 md:text-sm';
}

@Directive({ selector: 'label[uiLabel]', standalone: true })
export class UiLabel extends ClassMerge {
  protected readonly base =
    'text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70';
}

@Directive({ selector: '[uiCard]', standalone: true })
export class UiCard extends ClassMerge {
  protected readonly base = 'rounded-xl border bg-card text-card-foreground shadow';
}
@Directive({ selector: '[uiCardHeader]', standalone: true })
export class UiCardHeader extends ClassMerge {
  protected readonly base = 'flex flex-col space-y-1.5 p-6';
}
@Directive({ selector: '[uiCardTitle]', standalone: true })
export class UiCardTitle extends ClassMerge {
  protected readonly base = 'font-semibold leading-none tracking-tight';
}
@Directive({ selector: '[uiCardDescription]', standalone: true })
export class UiCardDescription extends ClassMerge {
  protected readonly base = 'text-sm text-muted-foreground';
}
@Directive({ selector: '[uiCardContent]', standalone: true })
export class UiCardContent extends ClassMerge {
  protected readonly base = 'p-6 pt-0';
}
@Directive({ selector: '[uiCardFooter]', standalone: true })
export class UiCardFooter extends ClassMerge {
  protected readonly base = 'flex items-center p-6 pt-0';
}

export const UI_CARD = [UiCard, UiCardHeader, UiCardTitle, UiCardDescription, UiCardContent, UiCardFooter] as const;

export const badgeVariants = cva(
  'inline-flex items-center rounded-md border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2',
  {
    variants: {
      variant: {
        default: 'border-transparent bg-primary text-primary-foreground shadow hover:bg-primary/80',
        secondary: 'border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80',
        destructive: 'border-transparent bg-destructive text-destructive-foreground shadow hover:bg-destructive/80',
        outline: 'text-foreground',
      },
    },
    defaultVariants: { variant: 'default' },
  },
);

@Directive({ selector: '[uiBadge]', standalone: true, host: { '[class]': 'computedClass()' } })
export class UiBadge {
  readonly variant = input<VariantProps<typeof badgeVariants>['variant']>('default');
  readonly userClass = input<ClassValue>('', { alias: 'class' });
  protected readonly computedClass = computed(() => cn(badgeVariants({ variant: this.variant() }), this.userClass()));
}
