def split_quran_into_suras(line_counts_file, ayas_file, output_dir):
    import os

    # Ensure the output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Read the number of lines for each sura
    with open(line_counts_file, 'r', encoding='utf-8') as f:
        line_counts = [int(line.strip().split()[1]) for line in f.readlines()]

    # Read all ayas
    with open(ayas_file, 'r', encoding='utf-8') as f:
        ayas = f.readlines()

    # Initialize the starting index
    start_index = 0

    # Iterate over each sura
    for sura_number, line_count in enumerate(line_counts, start=1):
        # Determine the ending index for the current sura
        end_index = start_index + line_count

        # Extract the ayas for the current sura
        sura_ayas = ayas[start_index:end_index]

        # Define the output file name
        output_file = f'{output_dir}{sura_number}.txt'

        # Write the sura ayas to the output file
        with open(output_file, 'w', encoding='utf-8') as f:
            f.writelines(sura_ayas)

        # Update the starting index for the next sura
        start_index = end_index

    print(f'Successfully split the Quran into {len(line_counts)} sura files.')

import sys
split_quran_into_suras(sys.argv[2], sys.argv[1], sys.argv[3])

