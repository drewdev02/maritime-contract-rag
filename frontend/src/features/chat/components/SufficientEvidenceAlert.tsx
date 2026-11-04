import { AlertTriangle } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/shared/components/ui/alert";

export function SufficientEvidenceAlert() {
  return (
    <Alert
      variant="destructive"
      className="border border-amber-300 dark:border-amber-800 bg-amber-50/80 dark:bg-amber-950/30 text-amber-900 dark:text-amber-200 rounded-md shadow-2xs"
    >
      <AlertTriangle className="h-4 w-4 text-amber-600 dark:text-amber-400" />
      <AlertTitle className="text-xs font-bold text-amber-900 dark:text-amber-300 font-sans">
        Abstención por Insuficiencia de Evidencia
      </AlertTitle>
      <AlertDescription className="text-xs text-amber-800 dark:text-amber-400 mt-1 leading-relaxed">
        Los contratos indexados no contienen información suficiente o con suficiente relevancia semántica para responder con rigor probatorio a esta consulta.
      </AlertDescription>
    </Alert>
  );
}
