import os
import subprocess
import re

target_bpf_functions = ['queued_spin_lock_slowpath','queued_spin_lock']


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

                    # for something like #define xxx \
                    #                       do{...}while(...)
                    if line.startswith("#define") and line.find("\\") > 0 and lines[int(line_number)].find("{") > 0 and lines[int(line_number)].find("}") > 0:
                        next_line = lines[int(line_number)]
                        pattern = r"\{(.*?)\}"
                        matches = re.findall(pattern, next_line)
                        output_list = [item.strip() for match in matches for item in match.split(';')]
                        print(f"next line : {output_list}")
                        return output_list

                    if line.startswith("#define") and not line.endswith("\\"):
                        start_index = i
                        end_index = i + 1
                        is_mapping = True
                        break
                    else:
                        start_marker = line
                        start_index = i+2
                        #print(f"{start_index}")
                        print(f"{line}")
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
        command1 = f"global -x {function_name}"
        command2 = "awk '{print $2,$3}'"
        command3 = "awk '/ include/ || / kernel/'"

        process1 = subprocess.Popen(command1, stdout=subprocess.PIPE, shell=True, cwd=target_directory)
        process2 = subprocess.Popen(command2, stdin=process1.stdout, stdout=subprocess.PIPE, shell=True, cwd=target_directory)
        process3 = subprocess.Popen(command3, stdin=process2.stdout, stdout=subprocess.PIPE, shell=True, cwd=target_directory)

        process2.stdout.close()
        process1.stdout.close()
        output = process3.communicate()[0].decode('utf-8')

        return output
    except subprocess.CalledProcessError as e:
        print(f"Error executing the command: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def find_call_stack(function_name,source_path):
    try:
        function_info = execute_global_command(function_name,source_path).strip()
        parts = function_info.split()
        print(f"{parts}")
        if len(parts) % 2 != 0:
            print("The list must be even length")
        else:
            for i in range(0,len(parts),2):
                line_number = parts[i]
                function_path = parts[i + 1]
                function_path = f"{source_path}/{function_path}"
                print(f"find {function_path}")
              content = find_function_content(function_path,function_name,line_number)
                arguments = find_function_arguments(function_path,function_name,line_number)
                print(f"content: {content}")
                callee = None
                for instruction in content:
                    instruction = instruction.strip()
                    #print(f"instruction : {instruction}")
                    index_of_parentheses = instruction.find("(")
                    if index_of_parentheses != -1:
                        callee = instruction[:index_of_parentheses].strip()
                        if callee in target_bpf_functions:
                            print ("End of Stack: Found")
                            return None
                        if callee.find("spin_lock") == -1:
                            # in case that it does not call directly but passing to it as argument
                            #print("not found in this function")
                            start = instruction.find("(")
                            end = instruction.rfind(")")

                            if start == -1 or end == -1:
                                print("error when parsing arguments")
                            else:
                                parameters = instruction[start + 1:end].split(",")
                                callee = find_call_stack_with_arguments(callee, source_path,parameters)
                                if callee is not None:
                                    print (f"found in callee: {callee}")
                                    find_call_stack(callee, source_path)


                        else:
                            print (f"callee : {callee}")
                            find_call_stack(callee, source_path)
                    else:
                        print("invalid function call")


    except Exception as e:
        print(f"An error occurred: {e}")


def find_call_stack_with_arguments(function_name,source_path, parameters):
    try:
        function_info = execute_global_command(function_name,source_path).strip()
        parts = function_info.split()
        if len(parts) % 2 != 0:
            print("The list must be even length")
        else:
            for i in range(0,len(parts),2):
                line_number = parts[i]
                function_path = parts[i + 1]
                function_path = f"{source_path}/{function_path}"
                #print(f"find {function_path}")
                #print(f"{line_number}")

                content = find_function_content(function_path,function_name,line_number)
                arguments = find_function_arguments(function_path,function_name,line_number)
                #print(f"content: {content}")
                #print(f"arguments : {arguments}")
                callee = None
                for instruction in content:
                    instruction = instruction.strip()
                    index_of_parentheses = instruction.find("(")
                    if index_of_parentheses != -1:
                        callee = instruction[:index_of_parentheses].strip()
                        if len(arguments) != 0 and callee in arguments:
                            which_arguments = arguments.index(callee)
                            callee = parameters[which_arguments]
                        if callee.find("spin_lock") != -1:
                            return callee

                    else:
                        print("invalid function call")
                return None


    except Exception as e:
        print(f"An error occurred: {e}")



if __name__ == "__main__":
    source_path = "/usr/src/linux-source-5.4.0"
    function_name = "spin_lock"
    find_call_stack(function_name,source_path)
