import csv


# Written completely by chat gpt, but the professor said it is allright, for such non- essential 
# stuff
def export_to_csv(data, filename):
    """Exports dicts, list of tuples, or list of dicts to a CSV file."""
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        if isinstance(data, dict):
            # Case 1: Simple dict or dict of dicts
            first_val = next(iter(data.values()))
            
            if isinstance(first_val, dict):
                # Dict of dicts
                fieldnames = ['id'] + list(first_val.keys())
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for key, subdict in data.items():
                    row = {'id': key}
                    row.update(subdict)
                    writer.writerow(row)
            else:
                # Simple dict
                writer = csv.writer(f)
                writer.writerow(['key', 'value'])
                for key, value in data.items():
                    writer.writerow([key, value])

        elif isinstance(data, list):
            # Case 2: List of tuples or list of dicts
            if all(isinstance(row, tuple) for row in data):
                writer = csv.writer(f)
                writer.writerows(data)

            elif all(isinstance(row, dict) for row in data):
                fieldnames = list(data[0].keys())
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for row in data:
                    writer.writerow(row)

            else:
                raise ValueError("List must contain only tuples or only dictionaries.")

        else:
            raise ValueError("Unsupported data type.")