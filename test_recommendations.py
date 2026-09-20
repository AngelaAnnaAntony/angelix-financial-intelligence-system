from app import create_app
from app.services.financial_recommendation_service import (
    FinancialRecommendationService,
)


app = create_app()


with app.app_context():

    print("Starting Financial Recommendation Service test...")

    service = FinancialRecommendationService()

    result = service.generate(6)

    print()
    print("=" * 70)
    print("FINANCIAL RECOMMENDATION SERVICE TEST")
    print("=" * 70)

    print()
    print("AVAILABLE:", result["available"])

    print(
        "HEALTH SCORE:",
        result["financial_health"]["score"],
    )

    print(
        "HEALTH LEVEL:",
        result["financial_health"]["health_level"],
    )

    print(
        "REPORTING PERIOD:",
        result["reporting_period"],
    )

    print()
    print("-" * 70)
    print("RECOMMENDATIONS")
    print("-" * 70)

    for index, recommendation in enumerate(
        result["recommendations"],
        start=1,
    ):

        print()
        print(
            f"{index}. {recommendation['title']}"
        )

        print(
            "   Priority:",
            recommendation["priority"],
        )

        print(
            "   Area:",
            recommendation["area"],
        )

        print(
            "   Observation:",
            recommendation["observation"],
        )

        print(
            "   Recommendation:",
            recommendation["recommendation"],
        )

        print(
            "   Evidence:",
            recommendation["evidence"],
        )

        print(
            "   Expected Focus:",
            recommendation["expected_focus"],
        )

        print(
            "   Confidence:",
            recommendation["confidence"],
        )

    print()
    print("-" * 70)
    print("DISCLAIMER")
    print("-" * 70)

    print(
        result["disclaimer"]
    )

    print()
    print("=" * 70)
    print("TEST COMPLETED SUCCESSFULLY")
    print("=" * 70)