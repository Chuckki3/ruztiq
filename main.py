from src.logging_config import setup_logging
from src.services.pipeline_service import PipelineService


def main():

    setup_logging()

    pipeline = PipelineService()

    pipeline.process_batch(batch_size=100)


if __name__ == "__main__":
    main()