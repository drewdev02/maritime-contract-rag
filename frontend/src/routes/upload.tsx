import { createFileRoute, useNavigate, Link } from "@tanstack/react-router";
import { FileDropzone } from "@/features/upload/components/FileDropzone";
import { Button } from "@/shared/components/ui/button";
import { ArrowRight, Anchor } from "lucide-react";

export const Route = createFileRoute("/upload")({
  component: UploadPage,
});

function UploadPage() {
  const navigate = useNavigate();

  return (
    <div className="flex flex-col gap-8 max-w-5xl w-full mx-auto py-4">
      {/* Encabezado Institucional de Mesa de Entrada */}
      <div className="text-center space-y-2">
        <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 font-mono text-[11px] border border-slate-200 dark:border-slate-700 mx-auto">
          <Anchor className="w-3.5 h-3.5 text-slate-500" />
          <span>PUERTO DE ENTRADA DOCUMENTAL</span>
        </div>
        <h2 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
          Ingesta de Contratos Marítimos
        </h2>
      </div>

      {/* Bahía de Atraque Documental / Dropzone */}
      <FileDropzone
        onSuccess={() => {
          setTimeout(() => {
            navigate({ to: "/documents", search: { status: undefined } });
          }, 1200);
        }}
      />

      {/* Enlace hacia el Registro Central */}
      <div className="flex justify-center pt-1">
        <Button
          variant="outline"
          asChild
          className="text-xs text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white border-slate-200 dark:border-slate-800 h-8 px-3 rounded"
        >
          <Link to="/documents">
            <span>Ver catálogo de contratos registrados</span>
            <ArrowRight className="w-3.5 h-3.5 ml-1.5 opacity-60" />
          </Link>
        </Button>
      </div>
    </div>
  );
}
