import subprocess
import time
import shutil
import os

base_directory = "/home/syncord/SynCord-linux-base" 

def create_bpf_header(destination_path,my_bpf_path):
    destination_function_path = destination_path + "/" + my_bpf_path
    with open(destination_function_path, 'a') as destination_file:
        destination_file.write("#ifndef MY_BPF_SPIN_H\n")
        destination_file.write("#define MY_BPF_SPIN_H\n")

def end_bpf_header(destination_path,my_bpf_path):
    destination_function_path = destination_path + "/" + my_bpf_path
    with open(destination_function_path, 'a') as destination_file:
        destination_file.write("#endif")


def execute_command(command):
    process1 = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)

if __name__ == "__main__":
    execute_command("./filter_target_function.sh")
    execute_command("echo "" >  lock_def.txt")
    time.sleep(3)
    with open('/home/syncord/DMon-TCLock/benchmarks/DMon_filter/scripts/contend_func.txt', 'r') as file:
        for line in file:
            pos = line.find('+')
            if pos != -1:
                target_function = line[:pos]
                print(target_function)
                try:
                    command1 = f"cscope -dL -1 {target_function}"
                    command2 = "awk '{print $1,$3}'"
   
                    process1 = subprocess.Popen(command1, stdout=subprocess.PIPE, shell=True, cwd=base_directory)
                    process2 = subprocess.Popen(command2, stdin=process1.stdout, stdout=subprocess.PIPE, shell=True, cwd=base_directory)
    
                    process1.stdout.close()
                    output = process2.communicate()[0].decode('utf-8').strip()
                    print(output)
                    if "spin_lock" not in target_function:
                        file_name, line_number = output.split()
                        process2.stdout.close()
                        # print(f"{file_name},{line_number}")
                   
                        # find_locking will write to lock_def.txt the lock statement
                        # from there we can extract the lock type and which structure it's calling
                        find_lock_command = f"./find_locking.sh {target_function} {line_number} {file_name}"
                        process3 = subprocess.Popen(find_lock_command,shell=True)
                except subprocess.CalledProcessError as e:
                    print(f"Error executing the command: {e}")
                except Exception as e:
                    print(f"An error occurred: {e}")
    time.sleep(4)
    lock_with_structure = []
    with open('/home/syncord/DMon-TCLock/benchmarks/DMon_filter/scripts/lock_def.txt', 'r') as file:
        for line in file:
            line = line.strip()
            skip = 0
            open_parenthesis_index = line.find('(')
            last_arrow_index = line.rfind("->")
            closing_parenthesis_index = line.rfind(")")
            comma_index = line.find(",")

            lock_name = line[:open_parenthesis_index].strip()
            
            if(open_parenthesis_index <= 0):
                continue

            if(comma_index > 0 and last_arrow_index > 0):
                lock_structure = line[last_arrow_index + len("->"):comma_index].strip()
            elif (last_arrow_index > 0):
                lock_structure = line[last_arrow_index + len("->"):closing_parenthesis_index].strip()
            else:
                continue

            if(line.endswith(";") and lock_name.startswith("spin_lock")):
                for pair in lock_with_structure:
                    if(lock_name == pair[0] and lock_structure == pair[1]):
                        skip = 1
                        break
                
                if(skip == 0):
                    lock_with_structure.append((lock_name,lock_structure,"",""))
            elif (line.endswith(";") and lock_name.startswith("spin_unlock")):
                for index,pair in enumerate(lock_with_structure):
                    if(pair[0] == "spin_lock" and lock_name == "spin_unlock" and lock_structure == pair[1]):
                        lock_with_structure[index] = (pair[0],pair[1],lock_name,lock_structure)
                    else:
                        maybe_lock = pair[0][9:]
                        maybe_unlock = lock_name[11:]
                        if(len(maybe_lock) > 0  and len(maybe_unlock) > 0 
                                and maybe_lock[0] == maybe_unlock[0] and lock_structure == pair[1]):
                            lock_with_structure[index] = (pair[0],pair[1],lock_name,lock_structure) 
                            break

    
    print(lock_with_structure)

    source_path = "/home/syncord/SynCord-linux-base" 
    template_path = "/home/syncord/SynCord-linux-template"
    destination_path = "/home/syncord/SynCord-linux-destination"
    DMON_dir = "/home/syncord/DMon-TCLock/benchmarks/DMon_filter/"
    my_bpf_path = f"include/linux/my_bpf_spin_lock.h"

    if os.path.exists(template_path):
        shutil.rmtree(template_path)
        print("template already exists")

    shutil.copytree(source_path,template_path)

    already_apply_patch = []
    apply_spin_lock = 0
    for pair in lock_with_structure:
        new_lock = 0
        lock_type = pair[0]
        lock_structure = pair[1]
        unlock_type = pair[2]

        found = any(lock_type == tup[0] for tup in already_apply_patch)
        if found in already_apply_patch:
            new_lock = 1
        else:
            already_apply_patch.append((lock_type,unlock_type))
        change_func_calling_lock_command = f"python3 apply_coccinelle.py {lock_type} {lock_structure} {unlock_type} {apply_spin_lock} 2>/dev/null"
        apply_spin_lock = 1
        process3 = subprocess.Popen(change_func_calling_lock_command,stdout=subprocess.PIPE,shell=True)
        output = process3.communicate()[0].decode('utf-8')
        print(output)

    # start writing a new header file
    if os.path.exists(destination_path):
        shutil.rmtree(destination_path)
        print("destination already exists")
    shutil.copytree(template_path, destination_path)

    create_bpf_header(destination_path,my_bpf_path)
    lock_unlock_pairs = ""
    for pair in already_apply_patch:
        lock_type = pair[0]
        unlock_type = pair[1]
        lock_unlock_pairs += lock_type + ","+ unlock_type +","
    lock_unlock_pairs = lock_unlock_pairs[:len(lock_unlock_pairs) - 1]

    change_lock_chain_command = f"python3 adapt_to_bpf.py {lock_unlock_pairs}"
    print(f"({lock_unlock_pairs})")
    length = len(lock_unlock_pairs.split(","))
    print(length)
    process4 = subprocess.Popen(change_lock_chain_command,stdout=subprocess.PIPE,shell=True)
    output = process4.communicate()[0].decode('utf-8')

    end_bpf_header(destination_path,my_bpf_path)
    # write ENDIF

    subprocess.Popen("diff -ruN SynCord-linux-base  SynCord-linux-destination > template.patch",stdout=subprocess.PIPE,shell=True,cwd='/home/syncord/')

