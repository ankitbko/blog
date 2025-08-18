import sys, re, os

logs = sys.stdin.read()

# Try multiple patterns to be resilient to Netlify CLI changes
# 1) Old format: "Website Draft URL: <url>"
patterns = [
	r"Website Draft URL:\s*(https://[^\s]+)",
	# 2) Any netlify.app URL in the logs (newer CLI prints a box with the URL on its own line)
	r"(https://[^\s]+\.netlify\.app[^\s]*)",
]

draft_url = None
for pat in patterns:
	m = re.search(pat, logs)
	if m:
		draft_url = m.group(1)
		break

if not draft_url:
	# As a last resort, try to find any https URL
	m = re.search(r"(https://[^\s]+)", logs)
	if m:
		draft_url = m.group(1)

assert draft_url, 'Was not able to find Draft URL in the logs:\n{}'.format(logs)

# Prefer new GitHub Actions output mechanism if available
gh_output = os.environ.get('GITHUB_OUTPUT')
if gh_output:
	with open(gh_output, 'a') as f:
		f.write(f"draft_url={draft_url}\n")
else:
	# Fallback for older runners
	print("::set-output name=draft_url::{}".format(draft_url))

