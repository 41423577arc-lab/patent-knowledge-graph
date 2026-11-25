"""P5: initial completeness inspection through the shared data interface."""
from core.data_loader import available_tables, load_table


def main():
    for name in available_tables():
        table = load_table(name)
        print(f"{name}: {len(table)} rows")
        if table.empty:
            print("No rows; completeness is not defined")
        else:
            missing = table.isna() | table.eq("")
            print((1 - missing.mean()).round(4).to_string())


if __name__ == "__main__":
    main()
