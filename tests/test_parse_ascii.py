from pathlib import Path

from src.ingestion.parse_ascii import parse_receivables_txt


def test_invoice_amount_uses_overdue_rub_current_balance(tmp_path: Path):
    source = tmp_path / "receivables.txt"
    source.write_text(
        "\n".join(
            [
                "ООО Test\t01.06.2026\t12:00:00",
                "Задолженность на дату\t01.06.2029",
                "Группа клиентов\tAll",
                "Для целей НО\tAll",
                (
                    "1\t2\tClient\t10.05.2026\tORD-1\tPRINT-1\tSYS-1\tARS_New\t"
                    "1000,00\tRUB\t20.05.2026\t12\t250,50\t0,00\tGroup"
                ),
            ]
        ),
        encoding="cp1251",
    )

    df, _ = parse_receivables_txt(source)

    assert df.loc[0, "overdue_amount_rub"] == 250.50
    assert df.loc[0, "invoice_amount"] == 250.50
