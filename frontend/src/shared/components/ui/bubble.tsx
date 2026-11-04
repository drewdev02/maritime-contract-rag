"use client"

import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/shared/utils/cn"

function BubbleGroup({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="bubble-group"
      className={cn("flex min-w-0 flex-col gap-2", className)}
      {...props}
    />
  )
}

const bubbleVariants = cva(
  "group/bubble relative flex w-fit max-w-[85%] min-w-0 flex-col gap-1 transition-colors leading-relaxed font-sans shadow-xs",
  {
    variants: {
      variant: {
        default:
          "bg-indigo-600 text-white rounded-2xl rounded-tr-xs p-4.5",
        muted:
          "bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl rounded-tl-xs p-4.5 text-slate-900 dark:text-slate-100",
        outline:
          "border border-slate-200 dark:border-slate-800 bg-background rounded-2xl p-4 text-foreground",
      },
      align: {
        start: "self-start",
        end: "self-end",
      },
    },
    defaultVariants: {
      variant: "muted",
      align: "start",
    },
  }
)

function Bubble({
  variant = "muted",
  align = "start",
  className,
  ...props
}: React.ComponentProps<"div"> & VariantProps<typeof bubbleVariants>) {
  return (
    <div
      data-slot="bubble"
      data-variant={variant}
      data-align={align}
      className={cn(bubbleVariants({ variant, align }), className)}
      {...props}
    />
  )
}

function BubbleContent({
  className,
  children,
  ...props
}: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="bubble-content"
      className={cn("w-fit max-w-full min-w-0 select-text leading-relaxed", className)}
      {...props}
    >
      {children}
    </div>
  )
}

export { BubbleGroup, Bubble, BubbleContent }
