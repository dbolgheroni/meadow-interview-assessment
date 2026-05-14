import json
import logging
import os

from fastapi import FastAPI

import inngest
import inngest.fast_api

import dotenv
import httpx
import resend


inngest_client = inngest.Inngest(
    app_id="interview-assessment-dbolgheroni",
    logger=logging.getLogger("uvicorn"),
)


@inngest_client.create_function(
    fn_id="get_movie_summary",
    trigger=inngest.TriggerEvent(event="meadow_api/movie.watched"),
)
async def get_movie_summary(ctx: inngest.Context):
    async def _get_movie(title: str) -> str:
        # In a proper CI/CD setup, this should be stored in an encrypted vault.
        try:
            api_key = os.environ["OMDB_API_KEY"]
        except KeyError:
            raise inngest.NonRetriableError("No OMDB_API_KEY found on .env")

        omdb_api_url = f"http://www.omdbapi.com/"

        async with httpx.AsyncClient() as client:
            response = await client.get(
                omdb_api_url, params={"apikey": api_key, "t": title}
            )

        # Most errors from OMDb API are reasonable to retry, like network
        # errors in general (connection, proxy, timeout errors) but not all
        # errors should be retried. For instance, if a movie does not exist,
        # retrying it would not make sense.
        #
        # However, not every API works the same. Some can return a 404 when
        # something is not found. Others return 200, and notify this in the
        # response.
        #
        # In the case for OMDb API, if the movie does not exist, it still
        # returns 200, but with a 'Response' property set as 'False'.
        response.raise_for_status()

        # Deserialize the JSON from the response, then treats the result like
        # a proper data structure to look for the property in the JSON.
        response_text = json.loads(response.text)

        ctx.logger.info(response_text)

        # Fail the function right away if the movie does not exist.
        if response_text["Response"] == "False":
            raise inngest.NonRetriableError("Movie not found")

        summary = response_text["Plot"]

        return summary

    # extract data from the event
    try:
        movie_title = ctx.event.data["movie_title"]
    except KeyError:
        raise inngest.NonRetriableError("No 'movie_title' in the input event")

    summary = await ctx.step.run("get_movie_step", _get_movie, movie_title)

    await ctx.step.invoke(
        "call_send_email",
        function=send_email_summary,
        data={"movie_plot_summary": summary},
    )


@inngest_client.create_function(
    fn_id="send_email_summary",
    trigger=inngest.TriggerEvent(event="app/send_email_summary"),
)
async def send_email_summary(ctx: inngest.Context):
    async def _send_email_summary(summary: str):
        try:
            resend.api_key = os.environ["RESEND_API_KEY"]
        except KeyError:
            ctx.logger.info("no RESEND_API_KEY on .env")
            raise

        params: resend.Emails.SendParams = {
            "from": "Meadow Interview Assessment <meadow@resend.dev>",
            "to": "dbolgheroni0@proton.me",  # hardcoded for now
            "subject": "Movie Summary",
            "html": f"<p><b>Movie summary:</b> {summary}",
        }

        r = await resend.Emails.send_async(params)

    summary = ctx.event.data["movie_plot_summary"]
    await ctx.step.run("send_email_step", _send_email_summary, summary)


dotenv.load_dotenv()

app = FastAPI()

inngest.fast_api.serve(app, inngest_client, [get_movie_summary, send_email_summary])
