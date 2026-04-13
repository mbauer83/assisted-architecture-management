# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "typer",
# ]
# ///

import secrets
import string
import typer
from pathlib import Path
from typing import Annotated, Optional

def main(
    n: Annotated[int, typer.Argument(help="Length of each ID")] = 6,
    count: Annotated[int, typer.Option("--count", "-c", help="Number of IDs to generate")] = 100,
    output: Annotated[Optional[Path], typer.Option("--output", "-o", help="File to save the IDs")] = None
):
    """
    Generates multiple random, URL-safe IDs.
    """
    alphabet = string.ascii_letters + string.digits + "-_"
    
    ids = []
    for _ in range(count):
        new_id = "".join(secrets.choice(alphabet) for _ in range(n))
        ids.append(new_id)

    output_text = "\n".join(ids)

    if output:
        output.write_text(output_text)
        print(f"Successfully wrote {count} IDs to {output}")
    else:
        print(output_text)

if __name__ == "__main__":
    typer.run(main)
