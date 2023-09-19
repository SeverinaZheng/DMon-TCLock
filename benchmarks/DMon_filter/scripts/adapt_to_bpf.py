import os
import sys
import shutil
import subprocess
import re

target_bpf_functions = ['queued_spin_lock_slowpath','queued_spin_lock','queued_spin_unlock_slowpath','queued_spin_unlock','down_write']
valid_call_tree = []
instructions_added = []
functions_added = []
function_header_added = []


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
                    # and void ...
                    #         __acquire(lock);
                    if line.endswith(";"):
                        return None
                    if line.endswith(")") and lines[int(line_number)].strip() == "__acquires(lock);":
                        return None
                    if line.endswith(")") and lines[int(line_number)].strip() == "__releases(lock);":
                        return None

                     # for something like #define ... __LOCK_IRQSAVE, which will go to acquire
                    if "__LOCK_" in line:
                        return None

                    if line.startswith("#define") and (not line.endswith("\\")):
                        start_index = i
                        end_index = i + 1
                        is_mapping = True
                        break
                    else:
                        start_marker = line
                        start_index = i+2
                        #print(f"dd{start_index}")
                        #print(f"dd{line}")
                if (line.startswith(end_marker) or line.strip().startswith("} while")) and start_marker is not None and end_index is None:
                    end_index = i
                    #print(f"end{end_index}")
                    break
            if start_index is not None and end_index is not None:
                if is_mapping:
                    parts = lines[start_index].split()
                    if len(parts) >= 3:
                        # defpart,key,mapping = parts
                        # print(f"mapping")
                        return [parts[len(parts)-1]]
                lines_between_markers = lines[start_index:end_index]
                return lines_between_markers
            else:
                return None

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


def find_function_signature(file_path, function_name,line_number):
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
                        return None

                    parameters = line[start + 1:end].split(",")
                    return line

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
        print(f"{function_name}")
        print(f"source files :{parts}")
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
                signature = find_function_signature(function_path,function_name,line_number)
                if (content is None):
                    continue
                print(f"content: {content}")
                callee = None
                found = False
                altered = ""
                for j,instruction in enumerate(content):
                    instruction = instruction.strip()
                    # print(f"instruction : {instruction}")
                    # get rid of comments
                    if(instruction.startswith("*")):
                        continue
                    # get rid of "return" 
                    if(instruction.startswith("return ")):
                        instruction = instruction[7:]
                        altered = "return "
                    # get rid of "}while...."
                    if("} while" in instruction):
                        print("while")
                        continue

                    index_of_parentheses = instruction.find("(")
                    index_of_assign = instruction.find("=")
                    if index_of_parentheses != -1:
                        if index_of_assign > 0:
                            callee = instruction[index_of_assign+1:index_of_parentheses].strip()
                            altered = instruction[:index_of_assign+1]
                        else:
                            callee = instruction[:index_of_parentheses].strip()
                        if callee in target_bpf_functions:
                            print (f"End of Stack: Found:{function_name},{j}")
                            add_valid_function(signature,function_path_part, line_number,j,instruction)
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
                                    para_index = callee_instruction.find("(")
                                    callee = callee_instruction[:para_index]
                                    if find_call_stack(callee, source_path,lock_unlock):
                                        # print(f"valid caller{callee},{function_name}, {function_path},{line_number},{j}")
                                        add_valid_function(signature,function_path_part, line_number,j,callee_instruction)
                                        found = True


                        else:
                            if find_call_stack(callee, source_path,lock_unlock):
                                # print(f"valid caller{callee},{function_name}, {function_path},{line_number},{j}")
                                add_valid_function(signature,function_path_part, line_number,j,instruction)
                                found = True
            return found



    except Exception as e:
        print(f"An error occurred: {e}")

def add_valid_function(signature,function_path,line_number, offset,instruction):
    function_info = function_path +","+ str(line_number) + "," + str(offset) + "," + instruction

    target_index = -1
    found = False
    if signature not in functions_added or instruction.strip(";") not in instructions_added:
        for index,tup in enumerate(valid_call_tree):
            if(function_path,str(line_number)) == tup[0]:
                target_index=index
                found = True
                valid_call_tree.pop(target_index)
                valid_call_tree.append((tup[0],tup[1],(str(offset),instruction) ))
                break
        if not found:
            valid_call_tree.append(( (function_path,str(line_number)),(str(offset),instruction) ))
        functions_added.append(signature)
        instructions_added.append(instruction.strip(";"))



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
                if content is None:
                    return None
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
                                    paraphrase_arguments = paraphrase_arguments + "("+para_param+")"
                            callee = callee + paraphrase_arguments
                            return callee 

                    # else:
                    #   print("invalid function call")
                return None


    except Exception as e:
        print(f"An error occurred: {e}")

def create_bpf_header(destination_path,my_bpf_path):
    destination_function_path = destination_path + "/" + my_bpf_path
    with open(destination_function_path, 'a') as destination_file:
        destination_file.write("#ifndef MY_BPF_SPIN_H\n")
        destination_file.write("#define MY_BPF_SPIN_H\n")

def end_bpf_header(destination_path,my_bpf_path):
    destination_function_path = destination_path + "/" + my_bpf_path
    with open(destination_function_path, 'a') as destination_file:
        destination_file.write("#endif")




def write_to_bpf_header(template_path, destination_path,my_bpf_path,lock_unlock):
    print(valid_call_tree)
    for function_info in valid_call_tree:
        function_path = function_info[0][0]
        line_number = function_info[0][1]
        instruction_list = function_info[1:]
        #instruction_list = sorted(instruction_list, key=lambda x: x[0])
        #offset = parts[2]
        #instruction = parts[3].strip()

        source_function_path = template_path +"/" + function_path
        destination_function_path = destination_path + "/" + my_bpf_path
        # print(f"{function_path},{line_number}")


        with open(source_function_path, 'r') as sourcefile:
            content = sourcefile.read()
            lines = content.splitlines()
            reach_function = False
            add_policy = []
            with open(destination_function_path, 'a') as destination_file:
                for i, line in enumerate(lines):
                    altered_name = False
                    for instruction_info in instruction_list:
                        offset = instruction_info[0]
                        instruction = instruction_info[1].strip()

                        if i == int(line_number)-1 and not altered_name:
                            if line.startswith("#define") and (not line.endswith("\\")):
                                line = rewrite(line,False,instruction,lock_unlock)
                                if(line is None):
                                    break
                                print(f"{line}")
                                destination_file.write(line)
                                destination_file.write("\n")
                                break
                            line = rewrite(line,True,instruction,lock_unlock)
                            if(line is None):
                                break
                            # if this line is broken, then need to add int policy to next line
                            if ")" not in line:
                                add_policy.append(int(line_number))
                            reach_function = True
                            altered_name = True

                        if reach_function and i == int(line_number) + int(instruction_info[0]) + 1:
                            line = rewrite(line,False,instruction_info[1],lock_unlock)
                    if reach_function:
                        if any(i == x for x in add_policy):
                            right_para = line.rfind(")")
                            line = line[:right_para] + ", int policy" + line[right_para:]

                        print(f"{line}")
                        print(destination_function_path)
                        destination_file.write(line)
                        destination_file.write("\n")
                    if line == "}":
                        reach_function = False
                    if line is not None and line.strip().startswith("} while"):
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
        left_para_index = function_name.find("(")
        right_para_index = function_name.rfind(")")
        if left_para_index > 0 and right_para_index > 0:
            args =  function_name[left_para_index+1:right_para_index]
            function_name = function_name[:left_para_index]

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
                if(part.strip("(") in function_header_added):
                    return None
                else:
                    function_header_added.append(part.strip("("))
                    part = "my_bpf_" + part
            elif lock_unlock in part:
                if(part.strip("(") in function_header_added):
                    return None
                else:
                    function_header_added.append(part.strip("("))
                    part = "bpf_" + part
            modified = modified + part + " "
        modified = modified.strip()
        if line.startswith("#define"):
            modified = modified + arguments + ", policy" + other_info
        elif ")" in line:
            if not line.startswith("static"):
                modified = "static " +  modified + arguments + ", int policy" + other_info
            else:
                modified = modified + arguments + ", int policy" + other_info
        else:
            if not line.startswith("static"):
                modified = "static " +  modified + arguments + other_info
            else:
                modified = modified + arguments + other_info

    
    # for situation: #define xxx aaa
    elif line.startswith("#define"):
        modified = ""
        parts = ["#define"]
        remaining_parts = re.split(r'\)', line[8:])
        remaining_parts = [substring.strip() + ')' for substring in remaining_parts if substring]
        parts = parts + remaining_parts
                
        for i,part in enumerate(parts):
            first_left_brac = part.find("(")
            first_right_brac = part.find(")")
            if first_right_brac > 0:
                dec_and_arg= part[:first_right_brac]
                remaining =  part[first_right_brac:]
                if i == 1 :
                    if(part[:first_left_brac].strip("(") in function_header_added):
                        print(part[:first_left_brac])
                        print(function_header_added)
                        return None
                    else:
                        function_header_added.append(part[:first_left_brac].strip("("))
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
        left_brac_index = line.find("(")
        if line[:left_brac_index] != function_name:
            #print("====")
            #print(line)
            #print(function_name)
            #print(args)
            #print("===")
            first_right_brac = line.find(";")
            remaining =  line[first_right_brac+1:]
            modified = leading_space + "bpf_"+function_name.strip() + "("+args + ",policy);" + remaining
        else:
            equal_index =line.find("=")
            before_equal = ""
            if equal_index > 0:
                 before_equal =line[:equal_index+1]
                 line = line[equal_index+2:]
            last_right_brac = line.rfind(")")
            dec_and_arg= line[:last_right_brac]
            remaining =  line[last_right_brac:]
            modified = leading_space + re.match(r"\s*", line).group() + before_equal + "bpf_" + dec_and_arg + ",policy" + remaining

    return modified










def run_all(input_function_name,corresponding_unlock, which_lock, which_unlock):
    template_path = "/home/syncord/SynCord-linux-template"
    destination_path = "/home/syncord/SynCord-linux-destination"
    my_bpf_path = f"include/linux/my_bpf_{which_lock}.h"


    find_call_stack(input_function_name,template_path, which_lock)
    write_to_bpf_header(template_path, destination_path,my_bpf_path,which_lock)
    global valid_call_tree 
    valid_call_tree = []

    if(which_unlock != "None"):
        find_call_stack(corresponding_unlock,template_path, which_unlock)
        write_to_bpf_header(template_path, destination_path,my_bpf_path,which_unlock)
        print(function_header_added)
        valid_call_tree = []
    


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python adapt_to_bpf.py <lock_unlock_funcs> <which_lock> <which_unlock>")
        sys.exit(1)
    lock_unlock_pairs_string = sys.argv[1]
    which_lock = sys.argv[2]
    which_unlock = sys.argv[3]
    lock_unlock_pairs =lock_unlock_pairs_string.split(",")
    if len(lock_unlock_pairs) % 2 != 0:
        print("The list must be even length")
    else:
        for i in range(0,len(lock_unlock_pairs)-1,2):
            lock_name = lock_unlock_pairs[i]
            unlock_name = lock_unlock_pairs[i+1]
            run_all(lock_name,unlock_name, which_lock, which_unlock)
