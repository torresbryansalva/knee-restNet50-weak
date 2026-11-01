## Diagrama de flujo del procesamiento (Pasos 0–9)

```text
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│ FUENTES (Kaggle: rsna-knee-abnormality-detection) — sin descargar los DICOM (~570 GB)       │
│   train.csv          4,407 estudios × 14  (StudyInstanceUID, Report, 12 etiquetas)          │
│   train_series.csv  24,371 series   × 5   (Study/Series UID, Fluid_Sensitive,               │
│                                            Fat_Suppression, Anatomical_Plane)               │
└──────────────────────────────────────────────┬──────────────────────────────────────────────┘
                                               ▼
┌─ PASO 1 · PRIMER VISTAZO ───────────────────────────────────────────────────────────────────┐
│  shape, tipos, unicidad de IDs · todo estudio tiene series y viceversa · sin nulos          │
└──────────────────────────────────────────────┬──────────────────────────────────────────────┘
                                               ▼
┌─ PASO 2 · ETIQUETAS ────────────────────────────────────────────────────────────────────────┐
│  valores 0 / 1 / NaN  (NaN = desconocido, NUNCA 0)                                          │
│  58 estudios GOLD con las 12 etiquetas   ·   4,349 sin ninguna                              │
│  prevalencia en gold (enriquecida) · co-ocurrencias con P(B|A)                              │
└──────────────────────────────────────────────┬──────────────────────────────────────────────┘
                                               ▼
┌─ PASO 3 · REPORTES (texto libre multilingüe) ───────────────────────────────────────────────┐
│  3.1 longitud (mediana 129 palabras)                                                        │
│  3.2 idioma con langdetect (seed 0, caché) → 9 idiomas: en es tr hr el de bg nl fr          │
│  3.3 idioma × gold → fr sin gold; de/nl con 2                                               │
│  3.4 NFKC: µ(micro) → μ(griega), NBSP → espacio                    ┐                        │
│  3.4b ∆(U+2206) → Δ(U+0394) · RTF: \'e0 → à, \'b0 → °, \~ → " "    ├─► columna Report_norm  │
│  3.5 sección de CONCLUSIÓN (encabezados por idioma + estrictos:    │                        │
│      INTERPRETATION:, ΔΙΑΓΝΩΣΗ) → 2,687 de 4,407 (61%)             ┘                        │
│  3.6 un reporte por idioma → retos: negación, sinónimos, grados, trampas                    │
└──────────────────────────────────────────────┬──────────────────────────────────────────────┘
                                               ▼
┌─ PASO 4 · SERIES ───────────────────────────────────────────────────────────────────────────┐
│  Fluid_Sensitive ≡ Fat_Suppression (misma variable) · 3–14 series/estudio (moda 5)          │
│  cobertura: Axial FS 100% · Sag noFS 96.8% · Cor FS 96.4% · Sag FS 94.2%                    │
│  SESGO DE PROTOCOLO: los centros alemanes casi no hacen Sagital FS (6.5%)                   │
└──────────────────────────────────────────────┬──────────────────────────────────────────────┘
                                               ▼
            ╔══════════════════════════════════════════════════════════════════╗
            ║ DECISIÓN: secuencia principal = SAGITAL FS                       ║
            ║ elegibles = con ≥1 Sagital FS → 4,150 estudios (56 de 58 gold)   ║
            ║ excluidos 257 (95% alemanes) → se declara como sesgo             ║
            ╚════════════════════════════════╤═════════════════════════════════╝
                                             ▼
┌─ PASO 5 · MUESTRA PARA LEER A MANO ─────────────────────────────────────────────────────────┐
│  100 estudios elegibles y NO gold (sin fuga de información), estratificados por idioma      │
│  (proporcional, mínimo 5 por idioma, seed 42) → muestra_train_100.csv / muestra_series_100  │
└──────────────────────────────────────────────┬──────────────────────────────────────────────┘
                                               ▼
┌─ PASO 6 · TABLAS LIMPIAS (+ asserts) ───────────────────────────────────────────────────────┐
│  data/clean/train_clean.parquet   (4,407 × 27)  idioma, es_gold, elegible, Report_norm,     │
│                                                 conclusion, texto_extractor, combos         │
│  data/clean/series_clean.parquet  (24,371 × 9)  combo plano+secuencia, es_sagital_fs        │
└──────────────────────────────────────────────┬──────────────────────────────────────────────┘
                                               ▼
┌─ PASO 7 · EXTRACTOR DE ETIQUETAS DÉBILES (reglas diseñadas SOLO con la muestra de 100) ─────┐
│                                                                                             │
│   Report_norm ──► para_buscar() ──► oraciones() ──► ¿antecedente? ──sí──► se ignora (D6)    │
│                   minúsculas,       corta en . ; !   ("antecedentes                         │
│                   sin tildes (D4)   ?, ").x", "x.y",  clínicos:")                           │
│                                     viñetas (D3)            │ no                            │
│                                                             ▼                               │
│        ┌──────────────── CLASIFICADORES POR ORACIÓN (1 / 0 / -1 / None) ───────────────┐    │
│        │ 7.1-7.4  ACL ............ menciones solo/grupo · rotura · L1-L4               │    │
│        │ 7.5      Effusion ....... grado E1 · intraarticular E2 · "x: no" E3 · E4      │    │
│        │ 7.6      Baker's ........ B1-B3 · clasificador_hallazgo() genérico            │    │
│        │ 7.7      Contusion ...... C1-C4 (edema traumático vs degenerativo)            │    │
│        │          Fracture ....... F1-F2 (avulsión ósea, antigua = -1)                 │    │
│        │ 7.8      Meniscos M/L ... M1-M7 · LADO por mención + arrastre                 │    │
│        │ 7.9      OA M/L/PF ...... A1-A9 · COMPARTIMENTO · grados de cartílago         │    │
│        │ 7.10     MCL ............ K1-K5   ·   Synovitis ... S1-S3                     │    │
│        │  ─────────────────────────────────────────────────────────────────────────    │    │
│        │  piezas comunes: negado() [antes · turco/inglés detrás · tras ":"]            │    │
│        │                  dudoso() [antes · dudas pospuestas]   NORMAL · regex()       │    │
│        └─────────────────────────────────────┬─────────────────────────────────────────┘    │
│                                              ▼                                              │
│   etiqueta_estudio(): manda el 1, luego el -1; sin mención → 0 (D2)    salida 1/0/-1 (D1)   │
│   fuente de texto = REPORTE COMPLETO para las 12 etiquetas (D5)                             │
│                                                                                             │
│  7.11  extraer_etiquetas(reporte) → los 4,407 en ~25 s                                      │
│        → data/clean/etiquetas_debiles.parquet  (4,407 × 16)                                 │
└──────────────────────────────────────────────┬──────────────────────────────────────────────┘
                                               ▼
┌─ PASO 8 · VALIDACIÓN CONTRA LOS 56 GOLD ELEGIBLES (requisito 1) ────────────────────────────┐
│  8.1 por etiqueta: acuerdo, IC95 Wilson, kappa, sensibilidad, especificidad                 │
│      tres tratos del -1:   como 0 → 0.826   ·   como 1 → 0.823   ·   excluido → 0.866       │
│      (antes de las correcciones: 0.820 / 0.818 / 0.859)                                     │
│  8.2 por idioma + lectura de desacuerdos                                                    │
│      ├─ ruido IRREDUCIBLE: Synovitis/Effusion/Fracture del gold no salen del texto          │
│      ├─ DEFINICIONES distintas (A3, C3, F1) → NO se tocan; las resuelve la política del -1  │
│      └─ 2 fallos de IMPLEMENTACIÓN → corregidos en el mismo extractor (declarados):         │
│           · E2 cortaba "suprapatellar | bursada" (54 turcos)  · duda griega "μπορούσε"      │
│  Política del -1 = (a) global; como 0 / como 1 / ignorado = FACTOR DE LA ABLACIÓN           │
└──────────────────────────────────────────────┬──────────────────────────────────────────────┘
                                               ▼
┌─ PASO 9 · DATA DE ENTRADA PARA LA CNN ──────────────────────────────────────────────────────┐
│  9.1 TABLA MAESTRA: 4,407 estudios con 12 etiquetas débiles (0 vacías; antes 52,188)        │
│      + 12 columnas _gold (solo los 58 gold) · 24,371 series                                 │
│                                    │                                                        │
│      ┌─────────────────────────────┼──────────────────────────────┐                         │
│      ▼                             ▼                              ▼                         │
│  elegibles NO gold 4,094     gold elegibles 56            no elegibles 257                  │
│      │                             │                     (sin Sagital FS)                   │
│      ▼                             │                                                        │
│  9.2 SELECCIÓN 600 (seed 42)       │                                                        │
│      cuota ≥60 positivos por       │                                                        │
│      etiqueta (de la más rara)     │                                                        │
│      + relleno por idioma          │                                                        │
│      │            └──► 3,494 de reserva (no_usado)                                          │
│      ▼                             │                                                        │
│  9.3 TRAIN / VAL por estudio       │                                                        │
│      estratificación iterativa     │                                                        │
│      ┌──────┴──────┐               │                                                        │
│      ▼             ▼               ▼                                                        │
│   TRAIN 480     VAL 120        TEST 56                                                      │
│   débiles       débiles        gold                                                         │
│   1/0/-1        1/0/-1         1/0                                                          │
│      └─────────────┴───────┬───────┘                                                        │
│                            ▼                                                                │
│  9.4 series Sagital FS a leer: 750 de 656 estudios (93 con varias → la de MÁS cortes)       │
│  9.5 TABLA CNN + destino en la tabla maestra → data/cnn/                                    │
│        dataset_cnn.csv            (656 × 17)   ← ENTRADA DE LA CNN                          │
│        series_cnn.csv             (750 × 3)    ← qué DICOM leer en Kaggle                   │
│        train_completo.csv         (4,407 × 33) ← todo el dataset, con destino               │
│        train_series_completo.csv  (24,371 × 11)                                             │
│  9.6 figura p9_prevalencia_splits.png                                                       │
└──────────────────────────────────────────────┬──────────────────────────────────────────────┘
                                               ▼
               ┌──────────────────────────────────────────────────────────────┐
               │ SIGUIENTE · KAGGLE NOTEBOOK                                  │
               │ leer DICOM → desempate por cortes → cortes 2D/2.5D en .npy   │
               │ → Dataset PyTorch → CNN desde cero / transfer learning       │
               └──────────────────────────────────────────────────────────────┘
```

**Leyenda de reglas.**
D = generales (D1 salida 1/0/−1 · D2 sin mención = 0 · D3 oración · D4 sin tildes · D5 reporte completo · D6 sin antecedentes).
L = ACL · E = Effusion · B = Baker's · C = Contusion · F = Fracture · M = Meniscos · A = Artrosis · K = MCL · S = Synovitis.
El detalle de cada regla está en el bloque `REGLAS DE ETIQUETADO` de su celda.
