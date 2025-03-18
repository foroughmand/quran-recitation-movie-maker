import re
import sys

def replace_numbers_in_file(file_path, regex_pattern, value):
    try:
        # Function to replace the matched numbers
        def replacer(match):
            number = float(match.group(1))  # Convert matched string to an integer
            # return str(number + value)  # Increment by 10 and convert back to string
            number = str(number + value)
            return match.group(0).replace(match.group(1), number)  # Replace only group(1)

        # Read the file content
        modified_contents = []
        with open(file_path, 'r', encoding='utf-8') as file:
            for line in file.readlines():
            # Perform replacement
                modified_line = re.sub(regex_pattern, replacer, line)
                modified_contents.append(modified_line)
        modified_content = ''.join(modified_contents)

        # Write back to file (or new file)
        #output_path = output_file if output_file else file_path
        #with open(output_path, 'w', encoding='utf-8') as file:
        with sys.stdout as file:
            file.write(modified_content)

    except Exception as e:
        print(f"Error: {e}")

# Example usage
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python script.py <file_path> <regex_pattern> <value>")
    else:
        file_path = sys.argv[1]
        regex_pattern = sys.argv[2]
        value = float(sys.argv[3])
        replace_numbers_in_file(file_path, regex_pattern, value)

