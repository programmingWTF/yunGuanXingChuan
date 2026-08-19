import * as React from "react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Checkbox } from "@/components/ui/checkbox"
import { Slider } from "@/components/ui/slider"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Progress } from "@/components/ui/progress"
import { Separator } from "@/components/ui/separator"
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs"
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { Progress as Bar } from "@/components/ui/progress"
import { Toaster } from "@/components/ui/toaster"

export default function UIShowcase() {
  const [progress, setProgress] = React.useState(62)

  return (
    <div className="mx-auto w-full max-w-5xl space-y-10 p-8">
      <TooltipProvider>
        <header className="space-y-2">
          <Badge variant="secondary">shadcn/ui · 他山设计系统</Badge>
          <h1 className="font-display text-3xl font-bold tracking-tight">组件展示页</h1>
          <p className="text-muted-foreground">
            落地 issue #100 —— shadcn/ui 整套组件 + Design Token，统一到他山世界学术风（宋体衬线 · 低饱和青蓝 · 大留白）
          </p>
        </header>

        <Separator />

        {/* 按钮 */}
        <section className="space-y-3">
          <h2 className="font-display text-xl font-semibold">Button 按钮</h2>
          <div className="flex flex-wrap items-center gap-3">
            <Button>默认按钮</Button>
            <Button variant="secondary">次要</Button>
            <Button variant="outline">描边</Button>
            <Button variant="ghost">幽灵</Button>
            <Button variant="destructive">危险</Button>
            <Button variant="link">链接</Button>
            <Button size="sm">小号</Button>
            <Button size="lg">大号</Button>
            <Button disabled>禁用</Button>
          </div>
        </section>

        {/* 徽标与徽章 */}
        <section className="space-y-3">
          <h2 className="font-display text-xl font-semibold">Badge / Alert 徽标与提示</h2>
          <div className="flex flex-wrap items-center gap-3">
            <Badge>默认</Badge>
            <Badge variant="secondary">次要</Badge>
            <Badge variant="destructive">危险</Badge>
            <Badge variant="outline">描边</Badge>
          </div>
          <Alert>
            <AlertTitle>提示标题</AlertTitle>
            <AlertDescription>这是一条默认的提示信息，用于说明当前状态的附加内容。</AlertDescription>
          </Alert>
          <Alert variant="destructive">
            <AlertTitle>错误提示</AlertTitle>
            <AlertDescription>某处发生了错误，请检查后重试。</AlertDescription>
          </Alert>
        </section>

        {/* 表单控件 */}
        <section className="space-y-3">
          <h2 className="font-display text-xl font-semibold">表单控件</h2>
          <div className="grid gap-6 rounded-lg border bg-card p-6 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="name">姓名</Label>
              <Input id="name" placeholder="请输入姓名" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="email">邮箱</Label>
              <Input id="email" type="email" placeholder="you@example.com" />
            </div>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2">
                <Checkbox id="terms" />
                <Label htmlFor="terms">我同意条款</Label>
              </div>
              <div className="flex items-center gap-2">
                <Switch id="airplane" />
                <Label htmlFor="airplane">飞行模式</Label>
              </div>
            </div>
            <RadioGroup defaultValue="a">
              <div className="flex items-center gap-2">
                <RadioGroupItem value="a" id="ra" />
                <Label htmlFor="ra">方案 A</Label>
              </div>
              <div className="flex items-center gap-2">
                <RadioGroupItem value="b" id="rb" />
                <Label htmlFor="rb">方案 B</Label>
              </div>
            </RadioGroup>
          </div>
        </section>

        {/* 滑块与进度 */}
        <section className="space-y-3">
          <h2 className="font-display text-xl font-semibold">Slider / Progress 滑块与进度</h2>
          <div className="space-y-6 rounded-lg border bg-card p-6">
            <Slider
              defaultValue={[progress]}
              onValueChange={(v) => setProgress(v[0])}
              max={100}
            />
            <Progress value={progress} />
            <p className="text-sm text-muted-foreground">当前进度：{progress}%</p>
          </div>
        </section>

        {/* Tabs */}
        <section className="space-y-3">
          <h2 className="font-display text-xl font-semibold">Tabs 标签页</h2>
          <Tabs defaultValue="overview" className="w-full">
            <TabsList>
              <TabsTrigger value="overview">概览</TabsTrigger>
              <TabsTrigger value="details">详情</TabsTrigger>
              <TabsTrigger value="notes">备注</TabsTrigger>
            </TabsList>
            <TabsContent value="overview" className="rounded-lg border bg-card p-6">
              概览内容……
            </TabsContent>
            <TabsContent value="details" className="rounded-lg border bg-card p-6">
              详情内容……
            </TabsContent>
            <TabsContent value="notes" className="rounded-lg border bg-card p-6">
              备注内容……
            </TabsContent>
          </Tabs>
        </section>

        {/* Accordion */}
        <section className="space-y-3">
          <h2 className="font-display text-xl font-semibold">Accordion 手风琴</h2>
          <Accordion type="single" collapsible className="w-full">
            <AccordionItem value="a">
              <AccordionTrigger>第一项</AccordionTrigger>
              <AccordionContent>这是手风琴第一项的内容。</AccordionContent>
            </AccordionItem>
            <AccordionItem value="b">
              <AccordionTrigger>第二项</AccordionTrigger>
              <AccordionContent>这是手风琴第二项的内容。</AccordionContent>
            </AccordionItem>
          </Accordion>
        </section>

        {/* Dialog / AlertDialog / Dropdown */}
        <section className="space-y-3">
          <h2 className="font-display text-xl font-semibold">Dialog / Dropdown 弹窗与菜单</h2>
          <div className="flex flex-wrap gap-3">
            <Dialog>
              <DialogTrigger asChild>
                <Button variant="outline">打开弹窗</Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>确认操作</DialogTitle>
                  <DialogDescription>此操作可能需要二次确认。</DialogDescription>
                </DialogHeader>
                <DialogFooter>
                  <Button variant="outline">取消</Button>
                  <Button>确定</Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>

            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button variant="destructive">危险操作</Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>你确定要删除吗？</AlertDialogTitle>
                  <AlertDialogDescription>删除后无法恢复。</AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>取消</AlertDialogCancel>
                  <AlertDialogAction>继续</AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline">下拉菜单</Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent>
                <DropdownMenuLabel>账号</DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem>个人资料</DropdownMenuItem>
                <DropdownMenuItem>设置</DropdownMenuItem>
                <DropdownMenuItem>退出登录</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </section>

        {/* Avatar + Tooltip */}
        <section className="space-y-3">
          <h2 className="font-display text-xl font-semibold">Avatar / Tooltip</h2>
          <div className="flex items-center gap-4">
            <Avatar>
              <AvatarImage src="https://github.com/shadcn.png" alt="avatar" />
              <AvatarFallback>SC</AvatarFallback>
            </Avatar>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button variant="ghost" size="icon">?</Button>
              </TooltipTrigger>
              <TooltipContent>
                <p>这是一个悬浮提示</p>
              </TooltipContent>
            </Tooltip>
          </div>
        </section>

        {/* 卡片 */}
        <section className="space-y-3">
          <h2 className="font-display text-xl font-semibold">Card 卡片</h2>
          <Card className="max-w-sm">
            <CardHeader>
              <CardTitle>云观星传</CardTitle>
              <CardDescription>他山世界 · 跨文化研究平台</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                基于 shadcn/ui 组件库与 Design Token 重构的统一设计系统，保持宋体衬线学术风。
              </p>
            </CardContent>
            <CardFooter>
              <Button size="sm">了解更多</Button>
            </CardFooter>
          </Card>
        </section>
      </TooltipProvider>
      <Toaster />
    </div>
  )
}
