# modelos/

Los `.pt` no se versionan en git (están en `.gitignore`). Se descargan desde la sección **Releases** del
repositorio y se colocan en esta carpeta:

- `resnet50_ajuste_fino.pt`: modelo final (AUC macro 0.779 en el test gold)
- `resnet50_extractor_fijo.pt`
- `vgg11_base.pt`

Los tres los genera `notebooks/04_entrenamiento.ipynb` en `/kaggle/working/`. En el README principal está cómo
cargarlos.
