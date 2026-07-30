from src.lambda.handler import lambda_handler


def main():

    event = {
        "batch_size": 10
    }

    response = lambda_handler(
        event,
        None,
    )

    print(response)


if __name__ == "__main__":
    main()