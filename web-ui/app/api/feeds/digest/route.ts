export const maxDuration = 300; // 5 minutes timeout for long-running digest generation

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const params = searchParams.toString();
  const url = `http://localhost:8111/api/feeds/digest${params ? `?${params}` : ''}`;

  const response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
    },
    signal: AbortSignal.timeout(290_000),
  });

  const data = await response.json();
  return Response.json(data, { status: response.status });
}
