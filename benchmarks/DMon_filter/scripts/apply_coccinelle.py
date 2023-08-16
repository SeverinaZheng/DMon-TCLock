import os
import shutil
import subprocess

source_directory = "/home/syncord/SynCord-linux-base"
destination_directory = "/home/syncord/SynCord-linux-template"
DMON_dir = "/home/syncord/DMon-TCLock/benchmarks/DMon_filter/"
which_lock = "lock1"


def copy_directory(source, destination):
    try:
        shutil.copytree(source, destination)
        print(f"Directory '{source}' copied to '{destination}'")
    except Exception as e:
        print(f"Error copying directory: {e}")

def apply_coccinelle(file_path,file_name):
    try:
        cocci_path = DMON_dir + "scripts/find_spin_lock.cocci"
        command = f"spatch --sp-file {cocci_path} {file_name} -o {file_name}"
        subprocess.Popen(command, stdout=subprocess.PIPE, shell=True, cwd=file_path)
        grep = f"grep -n 'spin_unlock([^)]*->file_lock)' {file_name}"
        p1 = subprocess.Popen(grep, stdout=subprocess.PIPE,shell=True, cwd=file_path)
        output,_ = p1.communicate()
        if output != b"":
            # Open the original file and the new file
            original_file_path = file_path + "/" + file_name
            new_file_path = file_path + "/new_file.c"

            # The new line to be added
            new_line = "#include <linux/my_bpf_spin_lock.h>\n"

            # Open the original file for reading and new file for writing
            with open(original_file_path, "r") as original_file, open(new_file_path, "w") as new_file:
                # Write the new line to the new file
                new_file.write(new_line)

                # Write the contents of the original file to the new file
                new_file.write(original_file.read())

            os.rename(new_file_path, original_file_path)


    except subprocess.CalledProcessError as e:
        print(f"Error applying Coccinelle: {e}")

def apply_template_patch():
    template_patch_path = DMON_dir + f"{which_lock}/template.patch"
    command = f"patch -p1 < {template_patch_path}"
    process = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True, cwd=destination_directory)



if __name__ == "__main__":

    if os.path.exists(destination_directory):
        shutil.rmtree(destination_directory)
    copy_directory(source_directory, destination_directory)
    apply_template_patch()

    for root, dirs, files in os.walk(destination_directory):
        for file in files:
            if file.endswith(".c"):
                file_path = os.path.join(root, file)
                dir_index = file_path.rfind("/")
                file_dir = file_path[:dir_index]
                if "bpf" in file_dir:
                    continue
                apply_coccinelle(file_dir,file)
