# Plantilla: GitHub Action para sincronizar memoria compartida → Wiki

Esta plantilla explica cómo configurar un GitHub Action en **cada repositorio**
que use el MCP de Historias de Usuario, para sincronizar automáticamente el
directorio `.hu-memory/shared/` con la wiki del repositorio en GitHub.

## Requisitos previos

1. **Habilitar la wiki** del repositorio en GitHub:
   - Settings → Features → ✅ Wikis
   - Crear al menos una página manualmente (puede ser la Home vacía)

2. **Permisos del token**: El `GITHUB_TOKEN` por defecto NO tiene permisos
   de escritura sobre la wiki. Hay dos opciones:

   **Opción A — PAT (Personal Access Token):**
   - Crear un PAT clásico con scope `repo` (incluye wikis)
   - Agregarlo como secret del repo: Settings → Secrets → `WIKI_TOKEN`

   **Opción B — GitHub App (recomendado para org):**
   - Crear una GitHub App con permiso `contents: write`
   - Instalarla en el repo y usar un action como `tibdex/github-app-token`

## Paso a paso

### 1. Crear el archivo del workflow

En el repositorio destino (el que usa el MCP), crear:

```
.github/workflows/sync-memory-to-wiki.yml
```

### 2. Copiar este contenido

```yaml
name: Sync Shared Memory to Wiki

# Solo se ejecuta manualmente desde la pestaña Actions
on:
  workflow_dispatch:
    inputs:
      dry_run:
        description: 'Solo mostrar qué se sincronizaría (sin escribir)'
        required: false
        default: 'false'
        type: choice
        options:
          - 'false'
          - 'true'

jobs:
  sync-to-wiki:
    runs-on: ubuntu-latest
    permissions:
      contents: read

    steps:
      - name: Checkout repo
        uses: actions/checkout@v4

      - name: Verificar que shared/ existe
        run: |
          if [ ! -d ".hu-memory/shared" ]; then
            echo "❌ No se encontró .hu-memory/shared/ en este repo."
            echo "   Ejecutar sync_shared_memory con action='export' desde el MCP primero."
            exit 1
          fi
          echo "✅ .hu-memory/shared/ encontrado"
          echo "Archivos a sincronizar:"
          find .hu-memory/shared -name "*.md" | sort

      - name: Clone wiki
        if: inputs.dry_run == 'false'
        run: |
          git clone https://x-access-token:${{ secrets.WIKI_TOKEN }}@github.com/${{ github.repository }}.wiki.git wiki
          echo "✅ Wiki clonada"

      - name: Sincronizar archivos
        if: inputs.dry_run == 'false'
        run: |
          # Crear estructura en la wiki
          mkdir -p wiki/memoria
          mkdir -p wiki/memoria/entidades
          mkdir -p wiki/memoria/flujos
          mkdir -p wiki/memoria/decisiones

          # Copiar README como página principal de memoria
          if [ -f ".hu-memory/shared/README.md" ]; then
            cp .hu-memory/shared/README.md wiki/memoria/Home.md
          fi

          # Copiar entidades
          if [ -d ".hu-memory/shared/entities" ]; then
            for f in .hu-memory/shared/entities/*.md; do
              [ -f "$f" ] && cp "$f" wiki/memoria/entidades/
            done
          fi

          # Copiar flujos
          if [ -d ".hu-memory/shared/flows" ]; then
            for f in .hu-memory/shared/flows/*.md; do
              [ -f "$f" ] && cp "$f" wiki/memoria/flujos/
            done
          fi

          # Copiar decisiones
          if [ -d ".hu-memory/shared/decisions" ]; then
            for f in .hu-memory/shared/decisions/*.md; do
              [ -f "$f" ] && cp "$f" wiki/memoria/decisiones/
            done
          fi

          echo "✅ Archivos copiados a wiki/"
          find wiki/memoria -name "*.md" | sort

      - name: Push a wiki
        if: inputs.dry_run == 'false'
        run: |
          cd wiki
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add -A
          if git diff --staged --quiet; then
            echo "ℹ️ Sin cambios — la wiki ya está al día."
          else
            COMMIT_MSG="Sync memoria compartida desde $(git -C .. rev-parse --short HEAD)"
            git commit -m "$COMMIT_MSG"
            git push
            echo "✅ Wiki actualizada exitosamente"
          fi

      - name: Dry run — mostrar cambios
        if: inputs.dry_run == 'true'
        run: |
          echo "🔍 DRY RUN — archivos que se sincronizarían:"
          echo ""
          echo "=== README ==="
          [ -f ".hu-memory/shared/README.md" ] && echo "  → wiki/memoria/Home.md"
          echo ""
          echo "=== Entidades ==="
          find .hu-memory/shared/entities -name "*.md" 2>/dev/null | while read f; do
            echo "  → wiki/memoria/entidades/$(basename $f)"
          done
          echo ""
          echo "=== Flujos ==="
          find .hu-memory/shared/flows -name "*.md" 2>/dev/null | while read f; do
            echo "  → wiki/memoria/flujos/$(basename $f)"
          done
          echo ""
          echo "=== Decisiones ==="
          find .hu-memory/shared/decisions -name "*.md" 2>/dev/null | while read f; do
            echo "  → wiki/memoria/decisiones/$(basename $f)"
          done
```

### 3. Configurar el secret

En el repositorio destino:

1. Ir a **Settings → Secrets and variables → Actions**
2. Click **New repository secret**
3. Name: `WIKI_TOKEN`
4. Value: Tu PAT con scope `repo`

### 4. Ejecutar

1. Ir a la pestaña **Actions** del repositorio
2. Seleccionar **"Sync Shared Memory to Wiki"**
3. Click **"Run workflow"**
4. Opcionalmente marcar dry_run para preview

## Estructura resultante en la wiki

```
wiki/
├── Home.md                    (página principal del repo — no se toca)
└── memoria/
    ├── Home.md                (README de la memoria compartida)
    ├── entidades/
    │   ├── poliza.md
    │   └── siniestro.md
    ├── flujos/
    │   └── registro-poliza.md
    └── decisiones/
        └── dn-001.md
```

## Notas

- El action **no tiene disparador automático**. Se ejecuta manualmente.
- La rama protegida garantiza que solo personas autorizadas pueden modificar
  `.hu-memory/shared/` — el action solo lee y copia a la wiki.
- Si quieres agregar un disparador automático en el futuro, agrega bajo `on:`:
  ```yaml
  push:
    branches: [main]
    paths: ['.hu-memory/shared/**']
  ```
- El dry_run permite verificar antes de escribir en la wiki.
