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
    fn_id="get_movie", trigger=inngest.TriggerEvent(event="meadow_api/movie.watched")
)
async def get_movie(ctx: inngest.Context):
    async def _get_movie(title: str) -> str:
        # get the API keys from an .env file
        # in a proper CI/CD setup, this should be stored in an encrypted vault
        try:
            api_key = os.environ["OMDB_API_KEY"]
        except KeyError:
            ctx.logger.info("no OMDB_API_KEY on .env")
            raise

        omdb_api_url = f"http://www.omdbapi.com/"

        async with httpx.AsyncClient() as client:
            response = await client.get(
                omdb_api_url, params={"apikey": api_key, "t": title}
            )

        response.raise_for_status()

        # deserialize the JSON from the response
        # then treats the result like a proper data structure
        response_text = json.loads(response.text)
        summary = response_text["Plot"]

        return summary

    # extract data from the event
    movie_title = ctx.event.data["movie_title"]

    summary = await ctx.step.run("get_movie_step", _get_movie, movie_title)

    await ctx.step.invoke(
        "call_send_email",
        function=send_email,
        data={"movie_plot_summary": summary},
    )


@inngest_client.create_function(
    fn_id="send_email", trigger=inngest.TriggerEvent(event="app/send_email")
)
async def send_email(ctx: inngest.Context):
    async def _send_email(summary: str):
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
    await ctx.step.run("send_email_step", _send_email, summary)


dotenv.load_dotenv()

app = FastAPI()

inngest.fast_api.serve(app, inngest_client, [get_movie, send_email])

inngest_client.send(inngest.Event(name="app/get_movie", data={}))
