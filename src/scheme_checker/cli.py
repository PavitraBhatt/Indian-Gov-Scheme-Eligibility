import argparse
from .core import EligibilityChecker, age_between


def main():
    parser = argparse.ArgumentParser(description="Scheme eligibility checker CLI")
    parser.add_argument("--age", type=int, required=True, help="Applicant age")
    args = parser.parse_args()

    applicant = {"age": args.age}
    scheme = {"name": "example"}

    checker = EligibilityChecker(rules=[age_between(18, 25)])
    ok = checker.is_eligible(applicant, scheme)
    print("ELIGIBLE" if ok else "NOT ELIGIBLE")


if __name__ == "__main__":
    main()
