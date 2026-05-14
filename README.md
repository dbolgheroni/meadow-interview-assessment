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

## Implmentation Details

The project uses `httpx` for making API calls, which uses an API compatible with `requests` but also support async calls.

The project uses Resend SDK to send emails, as per the task description, and uses the Python SDK instead of the Resend API. Using SDK instead of API speed up the development and can help in case of changes in the API.

There are two Inngest functions: `get_movie_summary` and `send_email_summary`.

Each function has an unique step. `get_movie_summary` is triggered by an event called `meadow_api/movie.watched`, such as this example:

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

Once the summary is extracted, `send_email_summary` is called, chaining the first call with the second call. This pattern follows a pattern similar to Celery chains explained here [here](https://docs.celeryq.dev/en/stable/userguide/canvas.html#chains).

Just keep in mind that Inngest functions are just regular decorated functions in code, can be async, but the concept is different is different than regular functions.

The regular functions being called are nested inside the Inngest functions. This helps keeping the code tight since it's small.

## Error handling

Inngest provide retries by default, configurable by functions and steps. The approach for error handling is using `response.raise_for_status()` and letting the function be retried by Inngest. The number of retries and debouncing is the default set by Inngest.

Resend Python SDK does not go deep into details on how to handle errors, but in case this becomes critical, probably would go down the route of using the Resend API to handle specific errors.

## Changes I would make if starting over

In retrospect, I would probably refactor to unify `get_movie_summary` and `send_email_summary` as a single function, calling both the OMDb API and sending the email as different steps.

The reason for this is because, once I cancel a function, the chained function won't hang doing attempts until it times out.

Doing a parallel with Temporal, it's like keeping a single Workflow to do both things, since they are part of the same "feature".

Temporal has the concept of Child Workflows that can span from the Parent Workflow. This has the advantage that, if the Parent Workflow is cancelled, the Child Workflows are cancelled too. This doesn't happen if a regular Workflow starts another regular Workflow.

Hardcoded email (or any other data) should not be in the code too.

## Other changes I would make when moving to production

I would also remove checking for the API keys in each function and would make sure all the needed keys are checked when the app is initializing. As stated in the code too, I would make sure the keys are not stored in a plain-text `.venv` file but on a proper encrypted vault or secret management library like Bitwarden.

Other changes would include keeping a proper file and dir structure and not everything on the main file of the project.

I would also probably use Pydantic for input event clean up. Fail earlier instead of checking how the event is structured every time part of the event data is used. This is an idea when I had developing, but later checking the documentation, there is in fact a guide for doing exactly this. :)

Inngest is very brief on testing information, but would make sure at tests are included too.

## Screnshots from UI

Inngest Functions:
![Functions](screenshots/screenshot-functions.png)

Apps:
![Apps](screenshots/screenshot-apps.png)

Sending event:
![Sending event](screenshots/screenshot-send-event.png)

Completed:
![Completed](screenshots/screenshot-completed.png)

Email received:
![Email received](screenshots/screenshot-email.png)

Failed function. Note the function is not retried. Also note the chained function to send email won't run:
![Non-existent movie](screenshots/screenshot-non-existent-movie.png)
