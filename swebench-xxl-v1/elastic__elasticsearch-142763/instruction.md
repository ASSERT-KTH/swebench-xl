# Task

## ES|QL TOP_SNIPPETS: Validate query argument is foldable at verification time

<h2>Business Goal</h2>
<p><code>TOP_SNIPPETS</code> takes a text field and a search query and extracts the most relevant passages. For example, if a user searches "machine learning," it highlights the best matching snippets from each result.</p>
<p>Currently, if a user passes a <strong>field</strong> instead of a search term - e.g., <code>TOP_SNIPPETS(description, title)</code> — we don't validate this. This means every row would search for something different (its own <code>title</code> inside its own <code>description</code>). We want to catch this mistake at compile time and show a clear error: <strong>"query must be a constant like a string, not a field."</strong></p>
<h2>Why This Is Required for semantic_text TOP_SNIPPETS</h2>
<p>To score chunks semantically, we convert the query into a vector. This is expensive. We can only do it <strong>once</strong> if the query is the same for every row. If the query changes per row, we'd call the AI model thousands of times  once per document  which is neither practical nor performant.</p>
<h2>Expected Behaviour</h2>

Expression | Result
-- | --
TOP_SNIPPETS(body, "search terms") | ✅ Works as before
TOP_SNIPPETS(body, title) | ❌ Compile-time error: query must be a constant
TOP_SNIPPETS(body, CONCAT("search", " terms")) | ✅ Works — the result is still a constant


<h2>Success Criteria</h2>
<p>The query argument must be validated as <strong>foldable</strong>. A foldable expression is one that is sufficient to evaluate only once for all rows:</p>
<ul>
<li><code>"search terms"</code> → foldable (literal constant)</li>
<li><code>CONCAT("abc", "def")</code> → foldable (all inputs are constants, result is the same for every row)</li>
<li><code>CONCAT(title, description)</code> → <strong>not foldable</strong> (inputs are fields from an Elasticsearch index, result varies per row)</li>
</ul>
<p>If the query argument is not foldable, the query should fail at <strong>compile time</strong> with a descriptive error message.</p>
<hr></body></html>

---

**Repo:** `elastic/elasticsearch`
**Base commit:** `ed24cd35ec6d00bbff2c9b2624eeb6daf5ae1746`
**Instance ID:** `elastic__elasticsearch-142763`
**Language:** `Java`
