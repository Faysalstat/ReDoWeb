import { Directive, computed, input } from '@angular/core';
import type { ClassValue } from 'clsx';

import { cn } from './cn';

/** Abstract base for fixed-class primitives: subclasses only declare their
 * base classes; the user's own `class` is merged on top with tailwind-merge. */
@Directive({ host: { '[class]': 'computedClass()' } })
export abstract class ClassMerge {
  protected abstract readonly base: string;
  readonly userClass = input<ClassValue>('', { alias: 'class' });
  // computed() is lazy, so the subclass's `base` is set before the first read
  protected readonly computedClass = computed(() => cn(this.base, this.userClass()));
}
