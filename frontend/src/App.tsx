import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

function App() {
  return (
    <div className="min-h-svh bg-background text-foreground grid place-items-center p-6">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>🧠 KnowField</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted-foreground">
            React + Vite + shadcn/ui 骨架已就緒。下一步：接 /api、重建 /chat。
          </p>
          <Button>沒事的按鈕</Button>
        </CardContent>
      </Card>
    </div>
  )
}

export default App
