#!/bin/bash

SOURCE_PATH=/home/syncord/SynCord-linux-base
TARGET_FUNCTION="$1"
TARGET_LINE="$2"
TARGET_FUNCTION_FILE="$3"
SEARCH_STRING=" $TARGET_FUNCTION("
# target=$(find $SOURCE_PATH -type f -name "*.c" -exec grep -H $SEARCH_STRING {} + | grep -v ';$')
# echo $target
# target_path="${target%%:*}"
target_path="$SOURCE_PATH/$TARGET_FUNCTION_FILE"
sig_set="()|*.&="
# echo $target_path
declare -A hash_table

if [ -r "$target_path" ]; then
    # Loop through each line of the file
    find_the_function=0
    line_number=0
    while IFS= read -r line; do
        ((line_number++))
        # Check if the line contains the desired substring
	if [[ $line == *"$SEARCH_STRING"* && $line_number == $TARGET_LINE
	       	&& $line != *";" && ($line == *")" || $line == *",") ]]; then
            # echo "Find the function '$TARGET_FUNCTION': $line: $line_number: $TARGET_LINE" >>lock_def.txt
            find_the_function=1
        fi

        if [ "$find_the_function" -eq 1 ]; then
            if [[ $line == "}" ]]; then
                # echo "$line:'$line_number'" >> lock_def.txt
                # echo "end of function '$TARGET_FUNCTION'" >> lock_def.txt
                find_the_function=0
            else
		# echo $line >> lock_def.txt
                if [[ $line == *"lock("* ]]; then
                    # echo "lock found '$line':'$line_number'"
                    # Extract the function name of the lock
                    func_name_with_brac=$(echo "$line" |  grep -oP "([^$sig_set()]*lock\()")
                    func_name=$(echo "$func_name_with_brac" |  grep -oP "[^\s]+lock")
		    echo $line >>lock_def.txt
		    echo $func_name >>lock_def.txt

                    # Distinguish between lock and unlock
                    if [[ $func_name == *"unlock"* ]];then
                        unlock_func_name=$(echo "$func_name" | grep -oP "[^\s]+(?=unlock)" | head -n1)
                        if [ -v "hash_table[$unlock_func_name]" ]; then
                            lock_name="${unlock_func_name}lock"
			    # echo "$lock_name"
                            echo "${hash_table[$unlock_func_name]} " >> lock_def.txt 

                        fi
                    else
                        lock_func_name=$(echo "$func_name" | grep -oP "[^\s]+(?=lock)" | head -n1)
                        hash_table[$lock_func_name]=$line
			echo $line >> lock_def.txt
                    fi
	    	elif [[ $line == *"down_write"* || $line == *"up_write"* || $line == *"up_read"* ]]; then
                    # Extract the function name of the lock
                    func_name_with_brac=$(echo "$line" |  grep -oP "([^$sig_set()]*\()")
                    func_name="${func_name_with_brac%?}"
		    echo $line >> lock_def.txt
                fi
            fi
        fi


    done < "$target_path"
else
    echo "Error: File '$target_path' does not exist or is not readable."
fi
