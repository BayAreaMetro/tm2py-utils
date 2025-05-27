#%%
from itertools import chain, pairwise
from pathlib import Path
import argparse
import py7zr
from tqdm import tqdm
from datetime import datetime
import subprocess

#%%

def archive(model_run_dir: Path | str, archive_dir: Path | str, name: str="", CHUNK_SIZE: int = 100):
    """
    archive a model run by compressing a certain outputs of a model run and storing them in the archive folder
    """

    # Coerce Types
    if isinstance(model_run_dir, str):
        model_run_dir = Path(model_run_dir)

    if isinstance(archive_dir, str):
        archive_dir = Path(archive_dir)

    # Get 7zip exe path, if you cant run this exe, you might be able to run another 
    seven_zip_path = (Path(__file__).parent.parent / "bin" / "7z.exe").resolve()
    assert seven_zip_path.exists(), f"expected to fine {seven_zip_path} but did not exist"
    
    # Get Name of the Archive File
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    if len(name) > 0:
        archive_name = f"{timestamp}_{name}"
    else:
        archive_name = f"{timestamp}"
    
    archive_path = archive_dir / f"{archive_name}.7z"

    
    # Here we create all the subdirectories we explicitly want to include 
    files_in_included_directories = list(
        chain(
            model_run_dir.glob("acceptance/**/*"), 
            model_run_dir.glob("CTRAMP/**/*"), 
            model_run_dir.glob("ctramp_output/**/*"), 
            model_run_dir.glob("demand_matrices/**/*"), 
            model_run_dir.glob("emme_project/**/*"), 
            model_run_dir.glob("inputs/**/*"), 
            model_run_dir.glob("logs/**/*"), 
            model_run_dir.glob("output_summaries/**/*"), 
        )
    )
    
    # list of directories we want to exclude
    excluded_sub_directories = list(
        chain(
            model_run_dir.glob("emme_project/*/emmemat"), 
        )
    )

    # exclude everything that that is'nt a file, and is in an excluded sub directory 
    files_to_archive = [file_to_archive.resolve() for file_to_archive in files_in_included_directories
        if (
            not any(
                file_to_archive.resolve().is_relative_to(dir_to_exclude.resolve())
                for dir_to_exclude in excluded_sub_directories
            )
        ) and (
            not file_to_archive.is_dir()
        )
    ]
    files_to_archive = [file.relative_to(model_run_dir) for file in files_to_archive]
    
    # using python bindings (above) is slower, we may be are better off just using 7z.exe
    for start, end in tqdm(
        list(
            pairwise(
                chain(
                    range(0, len(files_to_archive), CHUNK_SIZE), 
                    [len(files_to_archive)]
                )
            )
        )
    ):
        # zip a chunk size 
        cmd = [seven_zip_path, "a", str(archive_path)] + files_to_archive[start:end]

        process = subprocess.Popen(
            cmd,
            cwd=model_run_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        # Print or parse output line-by-line
        for line in process.stdout:
            print(line.strip())  # Could add parsing logic for progress indication

        process.wait()

        if process.returncode != 0:
            raise RuntimeError("7z command failed.")

    # Success we want to mark the current directory as archived
    with open(model_run_dir / "ARCHIVED.txt", "w") as file:
        file.write(f"This model run {archive_name} has been archived into:\n")
        file.write(f"{str(archive_path)}")
    print("Successfully Archived Model Run")



def parse_cli_archive(args):
    archive(args.model_directory, args.archive_directory, args.name)

def main():
    parser = argparse.ArgumentParser(description="Archive utility")
    parser.add_argument("model_directory", help="Directory of model run to archive")
    parser.add_argument("archive_directory", help="Directory where the models would like to be archived")
    args = parser.parse_args()

    # Your logic here
    archive(args.model_directory, args.archive_directory)

if __name__ == "__main__":
    main()