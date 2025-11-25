#!/usr/bin/env python3
"""
Categorize Content Types
Marks non-program records with appropriate content_type
"""
from src.database.connection import db

def categorize_content():
    """Categorize all records by content type"""
    db.connect()

    categories = {
        'eligibility_rule': [
            'Actively Engaged in Farming',
            'Adjusted Gross Income',
            'Cash-Rent Tenant',
            'Controlled Substance',
            'Foreign Persons',
            'Payment Eligibility',
            'Payment Eligibility and Payment Limitations',
            'Payment Limitations'
        ],
        'report': [
            'USDA Reports Commodity Weekly Loan Activity Report',
            'Commodity Loan Activity Reports',
            'Price Support Reports',
            'Organic Certification Cost Share Programs (OCCSP) 2010 Annual Report',
            'Organic Certification Cost Share Programs (OCCSP) 2011 Annual Report',
            'Organic Certification Cost Share Programs (OCCSP) 2012 Annual Report',
            'Organic Certification Cost Share Programs (OCCSP) 2013 Annual Report',
            'Organic Certification Cost Share Programs (OCCSP) 2014 Annual Report',
            'Organic Certification Cost Share Programs (OCCSP) 2016 Annual Report',
            'Organic Certification Cost Share Programs (OCCSP) 2017 Annual Report',
            'Organic Certification Cost Share Programs (OCCSP) 2018 Annual Report',
            'Organic Certification Cost Share Programs (OCCSP) 2019 Annual Report',
            'Organic Certification Cost Share Programs (OCCSP) 2020 Annual Report',
            'Organic Certification Cost Share Programs (OCCSP) 2021 Annual Report',
            'Organic Certification Cost Share Programs (OCCSP) 2022 Annual Report',
            'Organic Certification Cost Share Programs (OCCSP) 2023 Annual Report'
        ],
        'handbook': [
            '2-LP (Rev. 9) - Loans and LDPs for Peanuts Handbook',
            'Guidelines for 2019 and Subsequent Crop Years 1-PPG'
        ],
        'factsheet': [
            'FSA Farm Storage Facility Loan Program Servicing Options Factsheet',
            'Emergency Relief Program Phase 2 and Pandemic Assistance Revenue Program Comparison Factsheet'
        ],
        'notice': [
            'Organic Certification Cost Share Program (OCCSP) 2019 Notice of Funds Availability'
        ],
        'informational': [
            'Civil Rights',
            'Economic and Policy Analysis',
            'Farm Bill Home',
            'Financial Management Information',
            'Initiatives',
            'Laws and Regulations',
            'Outreach and Education',
            'Price Support Initiatives',
            'FSA Directives',
            'Farm Loans Overview',
            'Guaranteed Loans - Lender Toolkit',
            'Noninsured Crop Disaster Assistance Program (NAP) Related Information',
            'Dairy Margin Coverage Program Enrollment Information'
        ]
    }

    updated_counts = {}

    for content_type, names in categories.items():
        count = 0
        for name in names:
            # Update records matching this name (or starting with it for reports)
            if 'USDA Reports' in name or 'Annual Report' in name:
                # Match partial names for series
                result = db.execute(
                    "UPDATE programs SET content_type = %s WHERE program_name LIKE %s",
                    (content_type, f'%{name}%')
                )
            else:
                # Exact match
                result = db.execute(
                    "UPDATE programs SET content_type = %s WHERE program_name = %s",
                    (content_type, name)
                )
            count += 1

        updated_counts[content_type] = count
        print(f"✓ Marked {count} records as '{content_type}'")

    # Check remaining programs
    remaining = db.fetch_one("""
        SELECT COUNT(*) as count
        FROM programs
        WHERE content_type = 'program'
    """)

    print(f"\n{'='*60}")
    print(f"Content Categorization Complete:")
    print(f"{'='*60}")
    for content_type, count in updated_counts.items():
        print(f"  {content_type}: {count} records")
    print(f"  program (actual programs): {remaining['count']} records")
    print(f"{'='*60}")

    db.close()

if __name__ == "__main__":
    categorize_content()
