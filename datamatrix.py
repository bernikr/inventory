import base64
import csv
import uuid
from pathlib import Path

import ppf.datamatrix
from PIL import Image, ImageDraw

PIXEL_SIZE = 40
BORDER = 1

OUTPUT_FOLDER = Path(__file__).parent / "codes"



if __name__ == "__main__":
    OUTPUT_FOLDER.mkdir(exist_ok=True)
    for f in OUTPUT_FOLDER.iterdir():
        f.unlink()

    with (OUTPUT_FOLDER / f"index.csv").open("w", newline="") as csvfile:
        w = csv.writer(csvfile, delimiter=";")
        w.writerow(["file", "uuid", "uuid_b64"])
        for _ in range(64):
            uuid_obj = uuid.uuid4()
            uuid_b64 = base64.urlsafe_b64encode(uuid_obj.bytes).decode().replace("=", "")
            # uuid.UUID(bytes=base64.urlsafe_b64decode(s + "=="))

            dm = ppf.datamatrix.DataMatrix(uuid_b64)

            size = len(dm.matrix)
            img = Image.new("1", [(size + 2 * BORDER) * PIXEL_SIZE] * 2, 1)

            def t(x):
                return (BORDER + x) * PIXEL_SIZE

            d = ImageDraw.Draw(img)
            for x, y in (
                (x, y) for y, l in enumerate(dm.matrix) for x, c in enumerate(l) if c
            ):
                d.rectangle([t(x), t(y), t(x + 1) - 1, t(y + 1) - 1], fill=0)

            filename = f"{uuid_b64}.png"

            with (OUTPUT_FOLDER / filename).open("wb") as f:
                img.save(f, "PNG")
            w.writerow([filename, uuid_obj, uuid_b64])
