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

    if isinstance(model_run_dir, str):
        model_run_dir = Path(model_run_dir)

    if isinstance(archive_dir, str):
        archive_dir = Path(archive_dir)
    
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    if len(name) > 0:
        archive_name = f"{timestamp}_{name}"
    else:
        archive_name = f"{timestamp}"
    
    archive_path = archive_dir / f"{archive_name}.7z"

    
    # for now we want to start by including everything in the directory
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
    
    # we want to exclude these files because they are too large
    excluded_sub_directories = list(
        chain(
            model_run_dir.glob("emme_project/*/emmemat"), 
        )
    )

    # exclude everything that isnt a file or a directory
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
    
    # Create the .7z archive
    # with py7zr.SevenZipFile(archive_dir, 'w') as archive:
    #     archive.write(archive_items)
    # with py7zr.SevenZipFile(archive_path, mode='w') as archive:
    #     for file in tqdm(files_to_archive):
    #         arcname = file.relative_to(model_run_dir)
    #         archive.write(file, arcname)

    # using python bindings is slower, we may be are better off just using 7z.exe
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
        cmd = [r"C:\Users\USLP095001\code\MTC\tm2py-utils\bin\7z.exe", "a", str(archive_path)] + files_to_archive[start:end]

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

    print("Successfully Archived Model Run")
    with open(model_run_dir / "ARCHIVED.txt", "w") as file:
        # Write some text to the file
        file.write(f"This model run {archive_name} has been archived into:\n")
        file.write(f"{str(archive_path)}")



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