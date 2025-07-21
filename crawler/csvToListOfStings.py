import csv

def csvToStringList(filepath):
    string_list = []
    with open(filepath, newline='', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            # Join each row into a single string
            line = ','.join(row)
            string_list.append(line)
    return string_list[1:]