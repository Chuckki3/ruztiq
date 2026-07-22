from src.services.pipeline_service import PipelineService


def main():

    pipeline = PipelineService()

    pipeline.process_batch(batch_size=25)


if __name__ == "__main__":
    main()