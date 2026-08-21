"""Excel report generation for RFM analysis.

Single responsibility: turn a scored RFM DataFrame + per-segment summary
into a formatted multi-sheet .xlsx with a Summary sheet.
"""

from __future__ import annotations

import os
from datetime import datetime

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils.dataframe import dataframe_to_rows

COLOR_BLUE = "0000FF"  # headers
COLOR_YELLOW = "FFFF00"  # header fill
COLOR_GRAY = "F0F0F0"  # alternating rows


def _create_summary_sheet(data_dict: dict, title: str, author: str) -> pd.DataFrame:
    rows = [
        ["Report Title", title],
        ["Generated", datetime.now().strftime("%Y-%m-%d %H:%M")],
        ["Author", author],
        ["", ""],
        ["Sheets Included", ""],
    ]
    for sheet_name, df in data_dict.items():
        rows.append([f"  - {sheet_name}", f"{len(df)} rows"])
    rows.extend([["", ""], ["Quick Stats", ""]])
    total_rows = sum(len(df) for df in data_dict.values())
    rows.append(["Total Data Rows", total_rows])
    rows.append(["Number of Sheets", len(data_dict)])
    return pd.DataFrame(rows, columns=["Item", "Value"])


def _add_sheet(wb: Workbook, df: pd.DataFrame, sheet_name: str, is_summary: bool = False) -> None:
    ws = wb.create_sheet(title=sheet_name)
    for r_idx, row in enumerate(dataframe_to_rows(df, index=False, header=True), 1):
        for c_idx, value in enumerate(row, 1):
            cell = ws.cell(row=r_idx, column=c_idx, value=value)
            if r_idx == 1:
                cell.font = Font(bold=True, color=COLOR_BLUE)
                cell.fill = PatternFill(start_color=COLOR_YELLOW, fill_type="solid")
                cell.alignment = Alignment(horizontal="center", vertical="center")
            elif not is_summary and r_idx % 2 == 0:
                cell.fill = PatternFill(start_color=COLOR_GRAY, fill_type="solid")
            if isinstance(value, (int, float)) and r_idx > 1:
                if abs(value) >= 1000000:
                    cell.number_format = '#,##0,,"M"'
                elif abs(value) >= 1000:
                    cell.number_format = "#,##0"
                elif 0 < abs(value) < 1:
                    cell.number_format = "0.00%"
                else:
                    cell.number_format = "#,##0"
    for column in ws.columns:
        max_length = max((len(str(c.value)) for c in column if c.value is not None), default=0)
        letter = column[0].column_letter
        ws.column_dimensions[letter].width = min(max_length + 2, 50)


def generate_excel_report(
    data_dict: dict,
    output_path: str,
    title: str = "Analysis Report",
    author: str = "Data Analytics Team",
) -> str:
    """Generate a multi-sheet Excel report from {sheet_name: DataFrame}."""
    wb = Workbook()
    wb.remove(wb.active)
    _add_sheet(wb, _create_summary_sheet(data_dict, title, author), "Summary", is_summary=True)
    for sheet_name, df in data_dict.items():
        _add_sheet(wb, df, str(sheet_name)[:31])
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    wb.save(output_path)
    print(f"Report saved: {output_path}")
    return output_path


def generate_rfm_excel(
    rfm_data: pd.DataFrame,
    segment_summary: pd.DataFrame,
    output_path: str = "output/rfm_analysis.xlsx",
) -> str:
    """Generate the RFM segmentation Excel report (Summary + Segments + Customer_RFM)."""
    summary_df = pd.DataFrame(
        {
            "Metric": ["Total Customers", "Segments", "Avg RFM Score"],
            "Value": [
                len(rfm_data),
                rfm_data["Segment"].nunique(),
                round(rfm_data["RFMScore"].mean(), 2),
            ],
        }
    )
    data_dict = {
        "Summary": summary_df,
        "Segments": segment_summary,
        "Customer_RFM": rfm_data[
            [
                "customer_id",
                "R_Quartile",
                "F_Quartile",
                "M_Quartile",
                "RFMClass",
                "RFMScore",
                "Segment",
            ]
        ],
    }
    return generate_excel_report(
        data_dict,
        output_path,
        title="RFM Segmentation Analysis",
        author="Customer Analytics Team",
    )


if __name__ == "__main__":
    sample = {
        "Metrics": pd.DataFrame({"Metric": ["Users", "Revenue"], "Value": [10000, 500000]}),
        "Details": pd.DataFrame({"Category": ["A", "B"], "Count": [100, 200]}),
    }
    generate_excel_report(sample, "data/sample_report.xlsx")
