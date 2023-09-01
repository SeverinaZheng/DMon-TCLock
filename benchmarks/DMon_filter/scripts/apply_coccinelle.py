import os
import sys
import shutil
import subprocess

source_directory = "/home/syncord/SynCord-linux-base"
destination_directory = "/home/syncord/SynCord-linux-template"
DMON_dir = "/home/syncord/DMon-TCLock/benchmarks/DMon_filter/"
which_lock = ""
structure = ""


def copy_directory(source, destination):
    try:
        shutil.copytree(source, destination)
        print(f"Directory '{source}' copied to '{destination}'")
    except Exception as e:
        print(f"Error copying directory: {e}")

def apply_coccinelle(file_path,file_name):
    try:
        cocci_path = DMON_dir + f"scripts/cocci_scripts/{lock_type}_{structure}.cocci"
        command = f"spatch --sp-file {cocci_path} {file_name} -o {file_name}"
        subprocess.Popen(command, stdout=subprocess.PIPE, shell=True, cwd=file_path)
        grep = f"grep -n '{unlock_type}([^)]*->{structure})' {file_name}"
        p1 = subprocess.Popen(grep, stdout=subprocess.PIPE,shell=True, cwd=file_path)
        output,_ = p1.communicate()
        if output != b"":
            # Open the original file and the new file
            original_file_path = file_path + "/" + file_name
            new_file_path = file_path + "/new_file.c"

            # The new line to be added
            new_line = "#include <linux/my_bpf_spin_lock.h>\n"
            found_include = False
            inserted = False
            # Open the original file for reading and new file for writing
            with open(original_file_path, "r") as original_file, open(new_file_path, "w") as new_file:
                # Write the new line to the new file
                for line in original_file:
                    if line.startswith("#include"):
                        found_include = True
                    elif found_include and not line.startswith("#include") and not inserted:
                        new_file.write(new_line)
                        inserted = True
                    new_file.write(line)

            os.rename(new_file_path, original_file_path)


    except subprocess.CalledProcessError as e:
        print(f"Error applying Coccinelle: {e}")

def apply_template_patch():
    template_patch_path = DMON_dir + f"{which_lock}/template.patch"
    command = f"patch -p1 < {template_patch_path}"
    process = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True, cwd=destination_directory)



if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("Usage: python adapt_to_bpf.py <lock_type> <structure> <unlock> <apply_spin_lock>")
        sys.exit(1)

    lock_type = sys.argv[1]
    structure = sys.argv[2]
    unlock_type = sys.argv[3]
    new_lock = sys.argv[4]
    which_lock = "spin_lock"

    if new_lock == "0" :
        apply_template_patch()
        print(f"apply patch to {which_lock}")
    print(f"apply patch to {lock_type}")

    for root, dirs, files in os.walk(destination_directory):
        for file in files:
            if file.endswith(".c"):
                file_path = os.path.join(root, file)
                dir_index = file_path.rfind("/")
                file_dir = file_path[:dir_index]
                if "bpf" in file_dir:
                    continue
                apply_coccinelle(file_dir,file)
