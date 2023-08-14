import os
import shutil
import subprocess
import re

target_bpf_functions = ['queued_spin_lock_slowpath','queued_spin_lock','queued_spin_unlock_slowpath','queued_spin_unlock']
valid_call_tree = []
functions_added = []


def find_function_content(file_path, function_name,line_number):
    try:
        with open(file_path, 'r') as file:
            content = file.read()
            lines = content.splitlines()
            start_marker = None
            end_marker = "}"

            start_index = None
            end_index = None
            is_mapping = False

            for i, line in enumerate(lines):
                if i == int(line_number)-1:
                    # for something like #define xxx \
                    #                       lock(_lock)
                    if line.startswith("#define") and line.find("\\") > 0 and lines[int(line_number)].find("{") == -1:
                        next_line = lines[int(line_number)]
                        return [next_line]

                    # for something like #define xxx do { }while(0)
                    if line.startswith("#define") and ( "{ }" in line):
                        return None

                    # for something like #define xxx \
                    #                       do{...}while(...)
                    if line.startswith("#define") and line.find("\\") > 0 and lines[int(line_number)].find("{") > 0 and lines[int(line_number)].find("}") > 0:
                        next_line = lines[int(line_number)]
                        pattern = r"\{(.*?)\}"
                        matches = re.findall(pattern, next_line)
                        output_list = [item.strip() for match in matches for item in match.split(';')]
                        return output_list

                    # for something like void ... acquire(lock);
                    if line.endswith(";"):
                        return None


                    if line.startswith("#define") and (not line.endswith("\\")):
                        start_index = i
                        end_index = i + 1
                        is_mapping = True
                        break
                    else:
                        start_marker = line
                        start_index = i+2
                        # print(f"{start_index}")
                        # print(f"{line}")
                if line.startswith(end_marker) and start_marker is not None and end_index is None:
                    end_index = i
                    #print(f"{end_index}")
                    break
            if start_index is not None and end_index is not None:
                if is_mapping:
                    parts = lines[start_index].split()
                    if len(parts) == 3:
                        defpart,key,mapping = parts
                        #print(f"mapping")
                        return [mapping]
                lines_between_markers = lines[start_index:end_index]
                return lines_between_markers
            else:
                return None

            print("=" * 80)  # Separator for clarity
    except FileNotFoundError:
        print(f"Error: The file '{file_path}' could not be found.")
    except Exception as e:
        print(f"An error occurred: {e}")


def find_function_arguments(file_path, function_name,line_number):
    try:
        with open(file_path, 'r') as file:
            content = file.read()
            lines = content.splitlines()
            start_marker = None
            end_marker = "}"

            start_index = None
            end_index = None
            is_mapping = False

            for i, line in enumerate(lines):
                if i == int(line_number)-1:
                    start = line.find("(")
                    end = line.rfind(")")

                    if start == -1 or end == -1:
                        return []

                    parameters = line[start + 1:end].split(",")
                    return [param.strip() for param in parameters]

    except FileNotFoundError:
        print(f"Error: The file '{file_path}' could not be found.")
    except Exception as e:
        print(f"An error occurred: {e}")



def execute_global_command(function_name,target_directory):
    try:
        command1 = f"cscope -dL -1 {function_name}"
        command2 = "awk '{print $1,$3}'"
        command3 = "awk '/^(kernel\/|include\/)/'"
        command4 = "awk '!/debug/'"

        process1 = subprocess.Popen(command1, stdout=subprocess.PIPE, shell=True, cwd=target_directory)
        process2 = subprocess.Popen(command2, stdin=process1.stdout, stdout=subprocess.PIPE, shell=True, cwd=target_directory)
        process3 = subprocess.Popen(command3, stdin=process2.stdout, stdout=subprocess.PIPE, shell=True, cwd=target_directory)
        process4 = subprocess.Popen(command4, stdin=process3.stdout, stdout=subprocess.PIPE, shell=True, cwd=target_directory)

        process3.stdout.close()
        process2.stdout.close()
        process1.stdout.close()
        output = process4.communicate()[0].decode('utf-8')

        return output
    except subprocess.CalledProcessError as e:
        print(f"Error executing the command: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def find_call_stack(function_name,source_path,lock_unlock):
    try:
        function_info = execute_global_command(function_name,source_path).strip()
        parts = function_info.split()
        # print(f"source files :{parts}")
        if len(parts) % 2 != 0:
            print("The list must be even length")
        else:
            for i in range(0,len(parts)-1,2):
                line_number = parts[i+1]
                function_path_part = parts[i]
                function_path = f"{source_path}/{function_path_part}"
                # print(f"find {function_path}")
                # print(f"find {line_number}")
                content = find_function_content(function_path,function_name,line_number)
                arguments = find_function_arguments(function_path,function_name,line_number)
                if (content is None):
                    continue
                # print(f"content: {content}")
                callee = None
                found = False
                for j,instruction in enumerate(content):
                    instruction = instruction.strip()
                    # print(f"instruction : {instruction}")
                    index_of_parentheses = instruction.find("(")
                    if index_of_parentheses != -1:
                        callee = instruction[:index_of_parentheses].strip()
                        if callee in target_bpf_functions:
                            # print (f"End of Stack: Found:{function_name},{j}")
                            add_valid_function(function_path_part, line_number,j,instruction)
                            return True
                        if callee.find(lock_unlock) == -1:
                            # in case that it does not call directly but passing to it as argument
                            #print("not found in this function")
                            start = instruction.find("(")
                            end = instruction.rfind(")")

                            if start == -1 or end == -1:
                                print("error when parsing arguments")
                            else:
                                parameters = instruction[start + 1:end].split(",")
                                callee_instruction = find_call_stack_with_arguments(callee, source_path,parameters,lock_unlock)
                                if callee_instruction is not None:
                                    parts = callee_instruction.split(",")
                                    callee = parts[0]
                                    if find_call_stack(callee, source_path,lock_unlock):
                                        # print(f"valid caller{callee},{function_name}, {function_path},{line_number},{j}")
                                        add_valid_function(function_path_part, line_number,j,callee_instruction)
                                        found = True


                        else:
                            if find_call_stack(callee, source_path,lock_unlock):
                                # print(f"valid caller{callee},{function_name}, {function_path},{line_number},{j}")
                                add_valid_function(function_path_part, line_number,j,instruction)
                                found = True
            return found



    except Exception as e:
        print(f"An error occurred: {e}")

def add_valid_function(function_path,line_number, offset,instruction):
    function_info = function_path +","+ str(line_number) + "," + str(offset) + "," + instruction
    instruction = instruction.strip(";")
    if instruction not in functions_added and function_info not in valid_call_tree:
        valid_call_tree.append(function_info)
        functions_added.append(instruction)



def find_call_stack_with_arguments(function_name,source_path, parameters,lock_unlock):
    try:
        # print(f"argument {function_name}")
        function_info = execute_global_command(function_name,source_path).strip()
        parts = function_info.split()
        if len(parts) % 2 != 0:
            print("The list must be even length")
        else:
            for i in range(0,len(parts),2):
                line_number = parts[i+1]
                function_path_part = parts[i]
                function_path = f"{source_path}/{function_path_part}"
                # print(f"find {function_path}")
                # print(f"{line_number}")

                content = find_function_content(function_path,function_name,line_number)
                arguments = find_function_arguments(function_path,function_name,line_number)
                # print(f"content: {content}")
                # print(f"arguments : {arguments}")
                callee = None
                for instruction in content:
                    instruction = instruction.strip()
                    index_of_parentheses = instruction.find("(")
                    if index_of_parentheses != -1:
                        callee = instruction[:index_of_parentheses].strip()
                        if len(arguments) != 0 and callee in arguments:
                            which_arguments = arguments.index(callee)
                            callee = parameters[which_arguments]
                        if callee.find(lock_unlock) != -1:
                            paraphrase_arguments = ""
                            start = instruction.find("(")
                            end = instruction.rfind(")")

                            if start != -1 and end != -1:
                                raw_parameters = instruction[start + 1:end].split(",")
                            for param in raw_parameters:
                                 param = param.strip()
                                 if param in arguments:
                                    which_param = arguments.index(param)
                                    para_param = parameters[which_param]
                                    paraphrase_arguments = paraphrase_arguments + ","+para_param
                            callee = callee + paraphrase_arguments
                            return callee 

                    # else:
                    #   print("invalid function call")
                return None


    except Exception as e:
        print(f"An error occurred: {e}")


def create_bpf_header(template_path, destination_path,my_bpf_path,lock_unlock):
    for function_info in valid_call_tree:
        parts = function_info.split(',',3)
        function_path = parts[0]
        line_number = parts[1]
        offset = parts[2]
        instruction = parts[3].strip()

        source_function_path = template_path +"/" + function_path
        destination_function_path = destination_path + "/" + my_bpf_path
        # print(f"{function_path},{line_number}")


        with open(source_function_path, 'r') as sourcefile:
            content = sourcefile.read()
            lines = content.splitlines()
            reach_function = False
            with open(destination_function_path, 'a') as destination_file:
                for i, line in enumerate(lines):
                    if i == int(line_number)-1:
                        if line.startswith("#define") and (not line.endswith("\\")):
                            line = rewrite(line,False,instruction,lock_unlock)
                            print(f"{line}")
                            destination_file.write(line)
                            destination_file.write("\n")
                            break
                        line = rewrite(line,True,instruction,lock_unlock)
                        reach_function = True
                    if i == int(line_number) + int(offset) + 1:
                        line = rewrite(line,False,instruction,lock_unlock)
                    if reach_function:
                        print(f"{line}")
                        destination_file.write(line)
                        destination_file.write("\n")
                    if line == "}":
                        reach_function = False

                            
def rewrite(line, is_name,target_instruction,lock_unlock):
    function_name = ""
    args = ""
    if target_instruction.find("(") < 0:
        target_instruction = target_instruction.split(",",1)
        function_name = target_instruction[0]
        args = target_instruction[1]
    else:
        function_name = target_instruction
    modified = ""
    # rewrite function name
    if is_name:
        first_left_brac = line.find("(")
        first_right_brac = line.find(")")
        declaration = line[:first_left_brac+1]
        arguments = line[first_left_brac+1:first_right_brac]
        other_info = line[first_right_brac:]

        parts = declaration.split(' ')
        for part in parts:
            pattern = rf'^{re.escape(lock_unlock)}'
            if re.match(pattern,part) is not None:
                part = "my_bpf_" + part
            elif lock_unlock in part:
                part = "bpf_" + part
            modified = modified + part + " "
        modified = modified.strip()
        modified = modified + arguments + ", int policy" + other_info

    
    # for situation: #define xxx aaa
    elif line.startswith("#define"):
        modified = ""
        parts = line.split()
        for i,part in enumerate(parts):
            first_right_brac = part.find(")")
            if first_right_brac > 0:
                dec_and_arg= part[:first_right_brac]
                remaining =  part[first_right_brac:]
                modified = modified + "bpf_" + dec_and_arg + ",policy" + remaining + " "
            else:
                modified = modified + part + " "
    else:
        leading_space = ""
        for char in line:
            if char.isspace():
                leading_space += char
            else:
                break
        line = line.strip()
        # for situation: function passed as arguments
        if line != function_name:
            modified = leading_space + "bpf_"+function_name + "("+args + ",policy);"
        else:
            first_right_brac = line.find(")")
            dec_and_arg= line[:first_right_brac]
            remaining =  line[first_right_brac:]
            modified = leading_space + re.match(r"\s*", line).group() + "bpf_" + dec_and_arg + ",policy" + remaining

    return modified









if __name__ == "__main__":
    template_path = "/home/syncord/SynCord-linux-template"
    destination_path = "/home/syncord/SynCord-linux-destination"
    my_bpf_path = "include/linux/my_bpf_spin_lock.h"


    if os.path.exists(destination_path):
        print("destination already exists")
    else:
        shutil.copytree(template_path, destination_path)

    find_call_stack("spin_lock",template_path, "spin_lock")
    create_bpf_header(template_path, destination_path,my_bpf_path,"spin_lock")
    valid_call_tree = []

    find_call_stack("spin_unlock",template_path, "spin_unlock")
    create_bpf_header(template_path, destination_path,my_bpf_path,"spin_unlock")
    valid_call_tree = []
