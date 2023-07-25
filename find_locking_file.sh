#!/bin/bash

SOURCE_PATH=/usr/src/linux-source-5.4.0
TARGET_FUNCTION="fcntl_setlk"
SEARCH_STRING=" $TARGET_FUNCTION("
target=$(find $SOURCE_PATH -type f -name "*.c" -exec grep -H $SEARCH_STRING {} + | grep -v ';$')
#echo $target
target_path="${target%%:*}"
echo $target_path
declare -A hash_table


if [ -r "$target_path" ]; then
    # Loop through each line of the file
    find_the_function=0
    line_number=0
    while IFS= read -r line; do
        # Check if the line contains the desired substring
        if [[ $line == *"$SEARCH_STRING"* ]]; then
            echo "Find the function '$TARGET_FUNCTION': $line"
            find_the_function=1
        fi

        if [ "$find_the_function" -eq 1 ]; then
            if [[ $line == "}" ]]; then
                #echo "$line"
                echo "end of function '$TARGET_FUNCTION'"
                find_the_function=0
            else
                #echo "$line"
                ((line_number++))
                if [[ $line == *"lock("* ]]; then
                    hash_table[$line]=$line_number
                    echo "lock found '$line'"
                fi
            fi
        fi


    done < "$target_path"
else
    echo "Error: File '$target_path' does not exist or is not readable."
fi
