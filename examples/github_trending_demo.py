import asyncio
import datetime as dt
import json
import urllib.parse
import urllib.request

from synthflow.core.flow import Flow
from synthflow.core.node import Node, ResultRef


class FetchTrendingRepos(Node):
    async def run(self, days=7, top_n=10):
        since = (dt.date.today() - dt.timedelta(days=days)).isoformat()
        query = urllib.parse.urlencode(
            {
                "q": f"created:>={since}",
                "sort": "stars",
                "order": "desc",
                "per_page": top_n,
            }
        )
        url = f"https://api.github.com/search/repositories?{query}"
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "synthflow-github-trending-demo",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status != 200:
                raise RuntimeError(f"GitHub API request failed with status={resp.status}")
            payload = json.loads(resp.read().decode("utf-8"))
        return payload.get("items", [])


class FormatReposTable(Node):
    async def run(self, repos):
        headers = ["#", "repo", "stars", "lang", "updated", "url"]
        rows = [headers]

        for idx, repo in enumerate(repos, start=1):
            rows.append(
                [
                    str(idx),
                    repo.get("full_name", "-"),
                    str(repo.get("stargazers_count", 0)),
                    repo.get("language") or "-",
                    (repo.get("updated_at") or "-")[:10],
                    repo.get("html_url", "-"),
                ]
            )

        widths = [max(len(row[col]) for row in rows) for col in range(len(headers))]

        def format_row(row):
            return " | ".join(cell.ljust(widths[i]) for i, cell in enumerate(row))

        sep = "-+-".join("-" * width for width in widths)
        lines = [format_row(rows[0]), sep]
        lines.extend(format_row(row) for row in rows[1:])
        return "\n".join(lines)


class PrintReport(Node):
    async def run(self, text):
        print("GitHub trending repositories (recent):")
        print(text)
        return text


async def main():
    flow = Flow(
        FetchTrendingRepos(id="fetch").input(days=7, top_n=10)
        >> FormatReposTable(id="format").input(ResultRef("fetch"))
        >> PrintReport(id="print").input(ResultRef("format"))
    )
    await flow.run()


if __name__ == "__main__":
    asyncio.run(main())
