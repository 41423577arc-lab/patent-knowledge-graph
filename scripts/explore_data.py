"""P1: print current contract table sizes and missingness; no database required."""
from core.data_loader import available_tables, load_table


def main():
    for name in available_tables():
        table = load_table(name)
        print(name, len(table), table.isna().mean().round(3).to_dict())


if __name__ == "__main__":
    main()
