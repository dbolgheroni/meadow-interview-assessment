# Meadon Interview Assessment

The project uses `uv` as the Python package and project manager.

To initialize:
```
$ git clone dbolgheroni/meadow-interview-assessment
$ uv sync
```

The project reads the API keys from `.env` files and should search for the following keys:

- `OMDB_API_KEY`
- `RESEND_API_KEY`

## Run instructions

To run locally, a local Inngest server is needed:
```
npx --ignore-scripts=false inngest-cli@latest dev -u http://127.0.0.1:8000/api/inngest --no-discovery
```
It needs to have *npx* installed.

To run the app with `uv`:
```
(INNGEST_DEV=1 uv run uvicorn main:app --reload)
```

## Implmentation Rationale

### Libraries chosen

The project uses `httpx`, which uses an API compatible with `requests` but also support async calls.

The project uses Resend SDK, instead of making direct API calls. This should keep compatibility even the the API changes.

## Structure of function and steps

The project uses two functions: `get_movie_summary` and `send_email_summary`.

Each function has an unique step. `get_movie_summary` is triggered by an event called `meadow_api/movie_watched`, such as this example:

```
{
  "name": "meadow_api/movie.watched",
  "data": {
    "movie_title": "The Matrix",
    "recipient_email": "peter@test.com"
  }
}
```

Once triggered, `get_movie_summary` will hit OMDb API and extract the summary from the movie in the event.

The Inngest functions are triggered in many different ways, but in this project, `get_movie_summary` is triggered externally using the UI (can be also triggered by Python code), and the function `send_email_summary` is triggered by `get_movie_summary`.

Once extracted, `send_email_summary` is called, chaining the first call with the second call. This pattern follows a pattern similar to Celery chains explained here [here](https://docs.celeryq.dev/en/stable/userguide/canvas.html#chains).

Just keep in mind the Inngest functions are just regular decorated functions in code, can be async, but the concept is different.

## Error handling

Inngest provide retries by default, configurable by functions and steps. The approach for error handling is using `response.raise_for_status()` and letting the function be retried by Inngest.

Resend Python SDK does not go deep into details on how to handle errors, but in case this becomes critical, probably would go down the route of using the Resend API to handle specific errors.

## What I would do differently

In retrospect, I would probably refactor to unify `get_movie_summary` and `send_email_summary` as a single function, calling both the OMDb API and sending the email as different steps.

The reason for this is because, once I cancel a function, the other run won't hang doing attempts until it times out.

Doing a parallel with Temporal, it's like keeping a single Workflow to do both things, since they are part of the same "feature".

Temporal has the concept of Child Workflows that can span from the Parent Workflow. This has the advantage that, if the Parent Workflow is cancelled, the Child Workflows are cancelled too. This doesn't happen if a regular Workflow starts another regular Workflow.

## Screnshots from UI

![Functions](screenshots/screenshot-functions)
