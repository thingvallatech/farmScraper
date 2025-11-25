"""
Data Analysis & Gap Detection
Analyzes completeness and quality of collected data
"""
import logging
from typing import Dict, List, Any
from datetime import datetime
from pathlib import Path
import pandas as pd

from src.config import settings
from src.database.connection import db

logger = logging.getLogger(__name__)


class DataAnalyzer:
    """Analyze data completeness and identify gaps"""

    def __init__(self):
        self.report_data = {}

    def analyze_completeness(self) -> Dict[str, Any]:
        """
        Analyze what data we have vs what we need

        Returns:
            Dictionary with completeness metrics
        """
        logger.info("Analyzing data completeness...")

        # Use the view created in database
        query = "SELECT * FROM data_completeness_summary"
        summary = db.fetch_one(query)

        # Get more detailed breakdown
        detailed_query = """
            SELECT
                program_name,
                confidence_score,
                CASE WHEN payment_min IS NOT NULL THEN true ELSE false END as has_payments,
                CASE WHEN eligibility_parsed IS NOT NULL THEN true ELSE false END as has_eligibility,
                CASE WHEN application_end IS NOT NULL THEN true ELSE false END as has_deadline,
                source_url
            FROM programs
            ORDER BY confidence_score DESC
        """

        programs = db.fetch_all(detailed_query)

        # Calculate percentages
        total = summary['total_programs']

        if total > 0:
            payment_pct = (summary['programs_with_payments'] / total) * 100
            eligibility_pct = (summary['programs_with_eligibility'] / total) * 100
            deadline_pct = (summary['programs_with_deadlines'] / total) * 100
        else:
            payment_pct = eligibility_pct = deadline_pct = 0

        result = {
            'total_programs': total,
            'programs_with_payments': summary['programs_with_payments'],
            'programs_with_eligibility': summary['programs_with_eligibility'],
            'programs_with_deadlines': summary['programs_with_deadlines'],
            'payment_percentage': payment_pct,
            'eligibility_percentage': eligibility_pct,
            'deadline_percentage': deadline_pct,
            'high_confidence_programs': summary['high_confidence'],
            'low_confidence_programs': summary['low_confidence'],
            'avg_confidence': float(summary['avg_confidence']),
            'programs': programs,
        }

        self.report_data['completeness'] = result
        return result

    def analyze_payment_formats(self) -> Dict[str, int]:
        """Identify common payment description patterns"""
        query = "SELECT payment_info_raw, payment_unit FROM programs WHERE payment_info_raw IS NOT NULL"
        df = pd.read_sql(query, db._connection or db.connect())

        if df.empty:
            return {}

        patterns = {
            'per_acre': df['payment_info_raw'].str.contains('per acre', case=False, na=False).sum(),
            'percentage': df['payment_info_raw'].str.contains('%', case=False, na=False).sum(),
            'flat_rate': df['payment_info_raw'].str.contains('flat rate|lump sum', case=False, na=False).sum(),
            'formula_based': df['payment_info_raw'].str.contains('formula|calculation', case=False, na=False).sum(),
            'range_given': df['payment_info_raw'].str.contains(' to |between|-', case=False, na=False).sum(),
            'per_head': df['payment_info_raw'].str.contains('per head|per animal', case=False, na=False).sum(),
        }

        self.report_data['payment_patterns'] = patterns
        return patterns

    def analyze_eligibility_patterns(self) -> Dict[str, int]:
        """Analyze eligibility requirement patterns"""
        query = "SELECT eligibility_parsed FROM programs WHERE eligibility_parsed IS NOT NULL"
        rows = db.fetch_all(query)

        if not rows:
            return {}

        patterns = {
            'requires_farm_ownership': 0,
            'requires_acreage': 0,
            'income_limits': 0,
            'conservation_requirements': 0,
        }

        for row in rows:
            parsed = row['eligibility_parsed']
            if parsed:
                for key in patterns.keys():
                    if parsed.get(key):
                        patterns[key] += 1

        self.report_data['eligibility_patterns'] = patterns
        return patterns

    def identify_data_gaps(self) -> List[Dict[str, Any]]:
        """Identify programs with missing critical data"""
        query = """
            SELECT
                program_name,
                program_code,
                source_url,
                confidence_score,
                CASE WHEN payment_min IS NULL THEN 'payment_info' END as missing_payment,
                CASE WHEN eligibility_parsed IS NULL THEN 'eligibility' END as missing_eligibility,
                CASE WHEN application_end IS NULL THEN 'deadline' END as missing_deadline
            FROM programs
            WHERE payment_min IS NULL
                OR eligibility_parsed IS NULL
                OR application_end IS NULL
            ORDER BY confidence_score DESC
        """

        gaps = db.fetch_all(query)

        # Insert into data_gaps table for tracking
        for gap in gaps:
            missing_fields = []
            if gap.get('missing_payment'):
                missing_fields.append('payment_info')
            if gap.get('missing_eligibility'):
                missing_fields.append('eligibility')
            if gap.get('missing_deadline'):
                missing_fields.append('deadline')

            for field in missing_fields:
                importance = 'critical' if field == 'payment_info' else 'important'

                try:
                    db.execute(
                        """
                        INSERT INTO data_gaps (program_name, missing_field, field_importance, notes)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT DO NOTHING
                        """,
                        (gap['program_name'], field, importance,
                         f"Confidence: {gap['confidence_score']:.2f}")
                    )
                except Exception as e:
                    logger.error(f"Error inserting data gap: {e}")

        self.report_data['data_gaps'] = gaps
        return gaps

    def analyze_data_sources(self) -> Dict[str, Any]:
        """Analyze which sources provided the best data"""
        query = """
            SELECT
                SUBSTRING(source_url FROM 'https?://[^/]+') as domain,
                COUNT(*) as programs,
                AVG(confidence_score) as avg_confidence,
                COUNT(*) FILTER (WHERE payment_min IS NOT NULL) as with_payments,
                COUNT(*) FILTER (WHERE eligibility_parsed IS NOT NULL) as with_eligibility
            FROM programs
            GROUP BY domain
            ORDER BY avg_confidence DESC
        """

        sources = db.fetch_all(query)
        self.report_data['sources'] = sources
        return sources

    def get_high_quality_programs(self, min_confidence: float = 0.8) -> List[Dict]:
        """Get programs ready for production use"""
        query = """
            SELECT
                program_name,
                program_code,
                description,
                payment_min,
                payment_max,
                payment_unit,
                application_end,
                confidence_score,
                source_url
            FROM programs
            WHERE confidence_score >= %s
            ORDER BY confidence_score DESC
        """

        programs = db.fetch_all(query, (min_confidence,))
        return programs

    def generate_report(self) -> str:
        """Generate comprehensive analysis report"""
        logger.info("Generating analysis report...")

        # Run all analyses
        completeness = self.analyze_completeness()
        payment_patterns = self.analyze_payment_formats()
        eligibility_patterns = self.analyze_eligibility_patterns()
        gaps = self.identify_data_gaps()
        sources = self.analyze_data_sources()
        high_quality = self.get_high_quality_programs()

        # Build report
        report = f"""
================================================================================
FSA DATA COLLECTION REPORT
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
================================================================================

OVERVIEW
--------
Total Programs Found: {completeness['total_programs']}
High Confidence (>0.8): {completeness['high_confidence_programs']}
Low Confidence (<0.5): {completeness['low_confidence_programs']}
Average Confidence Score: {completeness['avg_confidence']:.3f}

DATA COMPLETENESS
-----------------
Programs with Payment Data: {completeness['programs_with_payments']} ({completeness['payment_percentage']:.1f}%)
Programs with Eligibility: {completeness['programs_with_eligibility']} ({completeness['eligibility_percentage']:.1f}%)
Programs with Deadlines: {completeness['programs_with_deadlines']} ({completeness['deadline_percentage']:.1f}%)

PAYMENT PATTERNS FOUND
----------------------
Per Acre Payments: {payment_patterns.get('per_acre', 0)}
Percentage-based: {payment_patterns.get('percentage', 0)}
Flat Rate: {payment_patterns.get('flat_rate', 0)}
Formula-based: {payment_patterns.get('formula_based', 0)}
Range Given: {payment_patterns.get('range_given', 0)}

ELIGIBILITY PATTERNS
--------------------
Requires Farm Ownership: {eligibility_patterns.get('requires_farm_ownership', 0)}
Requires Acreage: {eligibility_patterns.get('requires_acreage', 0)}
Income Limits: {eligibility_patterns.get('income_limits', 0)}
Conservation Requirements: {eligibility_patterns.get('conservation_requirements', 0)}

DATA QUALITY BY SOURCE
----------------------
"""
        for source in sources[:5]:
            report += f"{source['domain']}\n"
            report += f"  Programs: {source['programs']}\n"
            report += f"  Avg Confidence: {float(source['avg_confidence']):.3f}\n"
            report += f"  With Payments: {source['with_payments']}\n\n"

        report += f"""
HIGH-QUALITY PROGRAMS (Ready for Production)
---------------------------------------------
Programs with confidence >= 0.8: {len(high_quality)}

"""
        for prog in high_quality[:10]:
            report += f"- {prog['program_name']}"
            if prog['program_code']:
                report += f" ({prog['program_code']})"
            report += f" - Score: {prog['confidence_score']:.2f}\n"

        report += f"""

DATA GAPS (Programs Needing Manual Review)
-------------------------------------------
Programs with missing data: {len(gaps)}

Top 10 programs with missing data:
"""
        for gap in gaps[:10]:
            report += f"- {gap['program_name']} (Score: {gap['confidence_score']:.2f})\n"
            missing = []
            if gap.get('missing_payment'):
                missing.append('payment')
            if gap.get('missing_eligibility'):
                missing.append('eligibility')
            if gap.get('missing_deadline'):
                missing.append('deadline')
            report += f"  Missing: {', '.join(missing)}\n"

        # Success criteria evaluation
        report += f"""

SUCCESS CRITERIA EVALUATION
----------------------------
Target: 100+ FSA program pages
Actual: {completeness['total_programs']} programs
Status: {'✓ PASS' if completeness['total_programs'] >= 100 else '✗ FAIL'}

Target: Extract payment data for 30+ programs
Actual: {completeness['programs_with_payments']} programs
Status: {'✓ PASS' if completeness['programs_with_payments'] >= settings.min_payment_programs else '✗ FAIL'}

Target: Identify eligibility rules for 40+ programs
Actual: {completeness['programs_with_eligibility']} programs
Status: {'✓ PASS' if completeness['programs_with_eligibility'] >= settings.min_eligibility_programs else '✗ FAIL'}

Target: Find deadlines for 25+ programs
Actual: {completeness['programs_with_deadlines']} programs
Status: {'✓ PASS' if completeness['programs_with_deadlines'] >= settings.min_deadline_programs else '✗ FAIL'}

RECOMMENDATION
--------------
"""
        # Determine go/no-go
        meets_criteria = (
            completeness['total_programs'] >= 50 and
            completeness['programs_with_payments'] >= settings.min_payment_programs and
            completeness['avg_confidence'] >= settings.confidence_threshold
        )

        if meets_criteria:
            report += "GO - Sufficient data collected for production use.\n"
            report += f"Recommend proceeding with {len(high_quality)} high-quality programs.\n"
        else:
            report += "NO-GO - Insufficient data quality or quantity.\n"
            report += "Recommend manual data collection or refined extraction patterns.\n"

        report += "\n" + "=" * 80 + "\n"

        return report

    def save_report(self, report: str, filename: str = "extraction_report.txt"):
        """Save report to file"""
        output_path = settings.data_dir / filename

        try:
            output_path.write_text(report)
            logger.info(f"Report saved to {output_path}")
        except Exception as e:
            logger.error(f"Error saving report: {e}")

    def export_to_csv(self):
        """Export analyzed data to CSV files"""
        try:
            # Export programs
            query = "SELECT * FROM programs ORDER BY confidence_score DESC"
            df_programs = pd.read_sql(query, db._connection or db.connect())
            programs_csv = settings.data_dir / "programs_export.csv"
            df_programs.to_csv(programs_csv, index=False)
            logger.info(f"Programs exported to {programs_csv}")

            # Export data gaps
            query = "SELECT * FROM data_gaps ORDER BY field_importance, program_name"
            df_gaps = pd.read_sql(query, db._connection or db.connect())
            gaps_csv = settings.data_dir / "data_gaps_export.csv"
            df_gaps.to_csv(gaps_csv, index=False)
            logger.info(f"Data gaps exported to {gaps_csv}")

        except Exception as e:
            logger.error(f"Error exporting to CSV: {e}")


async def run_data_analysis():
    """Execute complete data analysis"""
    logger.info("Starting data analysis...")

    analyzer = DataAnalyzer()

    # Generate report
    report = analyzer.generate_report()

    # Print to console
    print(report)

    # Save to file
    analyzer.save_report(report)

    # Export CSVs
    analyzer.export_to_csv()

    logger.info("Data analysis complete")


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_data_analysis())
