from app import create_app

from app.services.financial_health_service import (
    FinancialHealthService,
)

from app.services.financial_recommendation_service import (
    FinancialRecommendationService,
)

from app.services.financial_ai_analysis_service import (
    FinancialAIAnalysisService,
)


app = create_app()


with app.app_context():

    print()
    print("=" * 70)
    print("ANGELIX AI FINANCIAL ANALYSIS TEST")
    print("=" * 70)

    organization_id = 6

    recommendation_service = (
        FinancialRecommendationService()
    )

    recommendation_result = (
        recommendation_service.generate(
            organization_id
        )
    )

    context = {
        "financial_health": (
            recommendation_result.get(
                "financial_health",
                {},
            )
        ),
        "analytics": (
            recommendation_result.get(
                "analytics",
                {},
            )
        ),
        "balance_sheet": (
            recommendation_result.get(
                "balance_sheet",
                {},
            )
        ),
        "reporting_period": (
            recommendation_result.get(
                "reporting_period",
                {},
            )
        ),
    }

    print()
    print("CONTEXT CREATED")
    print("-" * 70)

    print(
        "Health Score:",
        context["financial_health"].get(
            "score"
        ),
    )

    print(
        "Health Level:",
        context["financial_health"].get(
            "health_level"
        ),
    )

    print(
        "Reporting Period:",
        context["reporting_period"],
    )

    print(
        "Balance Sheet:",
        context["balance_sheet"],
    )

    service = FinancialAIAnalysisService()

    try:

        result = service.generate(
            context
        )

        print()
        print("-" * 70)
        print("AI SUMMARY")
        print("-" * 70)
        print(
            result["summary"]
        )

        print()
        print("-" * 70)
        print("AI INSIGHTS")
        print("-" * 70)

        for index, insight in enumerate(
            result["insights"],
            start=1,
        ):

            print()
            print(
                f"{index}. {insight['title']}"
            )

            print(
                "   Area:",
                insight["area"],
            )

            print(
                "   Observation:",
                insight["observation"],
            )

            print(
                "   Evidence:",
                insight["evidence"],
            )

            print(
                "   Implication:",
                insight["implication"],
            )

        print()
        print("-" * 70)
        print("AI OUTLOOK")
        print("-" * 70)

        print(
            result["outlook"]
        )

        print()
        print("=" * 70)
        print("AI FINANCIAL ANALYSIS TEST PASSED")
        print("=" * 70)

    except Exception as exc:

        print()
        print("=" * 70)
        print("AI FINANCIAL ANALYSIS TEST FAILED")
        print("=" * 70)

        print()
        print("ERROR:")
        print(str(exc))

        raise