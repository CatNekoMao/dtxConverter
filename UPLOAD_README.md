# Texture To DTX Upload Package

## Package Purpose

This package contains:

- `texture_to_dtx_converter.exe`
  Batch converts `bmp`, `jpg`, `jpeg`, `png`, and `tga` textures to `dtx`.
- `relink_project_textures_to_dtx.ms`
  3ds Max script that relinks scene bitmap textures to existing `.dtx` files under a chosen project folder.

## Files To Upload

Upload these files:

- `dist/texture_to_dtx_converter.exe`
- `max_texture_relink/relink_project_textures_to_dtx.ms`
- `UPLOAD_README.md`

Optional source files for archive/debug use:

- `texture_to_dtx_converter.py`
- `dtxutil.exe`

## Converter Behavior

`texture_to_dtx_converter.exe` will:

- scan the folder where the exe is placed, including subfolders
- support `bmp`, `jpg`, `jpeg`, `png`, and `tga`
- resize textures larger than `1024`
- pad non-square or non-power-of-two textures to a compatible square power-of-two size
- output converted files to `output_dtx`
- preserve original folder structure inside `output_dtx`
- show a progress window during processing
- write a log file named `convert_to_dtx.log`

## How To Use

### 1. Convert textures

1. Put `texture_to_dtx_converter.exe` into the texture root folder.
2. Double-click the exe.
3. Wait for the progress window to finish.
4. Check the generated `output_dtx` folder.

### 2. Relink in 3ds Max

1. Run `relink_project_textures_to_dtx.ms` in 3ds Max.
2. Pick the project texture folder that already contains `.dtx` files.
3. Click `Relink`.

## Notes

- The Max script only relinks existing `.dtx` files. It does not run the converter.
- Matching is based on texture file name without extension.
- If duplicate `.dtx` names exist in different folders, only the first indexed file is used.

## Recommended Delivery Structure

```text
texture_to_dtx_package/
  dist/
    texture_to_dtx_converter.exe
  max_texture_relink/
    relink_project_textures_to_dtx.ms
  UPLOAD_README.md
```
