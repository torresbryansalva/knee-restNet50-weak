# data/

Esta carpeta no se sube a GitHub (ver `.gitignore`). Aquí van los CSV de la competencia:

```bash
kaggle competitions download -c rsna-knee-abnormality-detection -f train.csv        -p data/
kaggle competitions download -c rsna-knee-abnormality-detection -f train_series.csv -p data/
```

El notebook `01_etiquetas_debiles.ipynb` genera dentro de esta carpeta:

| Archivo | Contenido |
|---|---|
| `clean/train_clean.parquet` | 4,407 × 27: reportes normalizados, idioma, gold, elegibilidad, conclusión |
| `clean/series_clean.parquet` | 24,371 × 9: series con combinación plano + secuencia |
| `clean/etiquetas_debiles.parquet` | 4,407 × 16: las 12 etiquetas débiles (1 / 0 / −1) |
| `cnn/dataset_cnn.csv` | 656 × 17: **entrada de la CNN** (split, idioma, 12 etiquetas) |
| `cnn/series_cnn.csv` | 750 × 3: series Sagital FS que se leen en Kaggle |
| `cnn/train_completo.csv` | 4,407 × 33: tabla maestra con el destino de cada estudio |
| `cnn/train_series_completo.csv` | 24,371 × 11: series con el destino de su estudio |

Todos contienen etiquetas derivadas de la competencia (incluidas las gold), por eso tampoco se suben.
