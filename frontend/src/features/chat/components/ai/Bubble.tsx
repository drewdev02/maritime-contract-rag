import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/shared/utils/cn"

const bubbleVariants = cva(
  "rounded-2xl p-4.5 text-sm transition-colors leading-relaxed font-sans shadow-xs",
  {
    variants: {
      variant: {
        user: "bg-indigo-600 text-white rounded-tr-xs",
        assistant: "bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-tl-xs text-slate-900 dark:text-slate-100",
      },
    },
    defaultVariants: {
      variant: "assistant",
    },
  }
)

export interface BubbleProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof bubbleVariants> {}

export const Bubble = React.forwardRef<HTMLDivElement, BubbleProps>(
  ({ className, variant, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(bubbleVariants({ variant }), className)}
        {...props}
      />
    )
  }
)
Bubble.displayName = "Bubble"
