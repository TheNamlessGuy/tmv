# Tag My Value

Tag strings and query for them.

## Usage

### Tagging

Send a post request to /tag with a payload formatted as follows:
```json
{
  "value": "value to tag",
  "multi_tags": ["tag3", "tag4"],
  "value_tags": [{"name": "tagN", "value": 5}, {"name": "tagN", "value": 6}]
}
```
Where the different *_tags are all optional, but at least one is required.

### Fetching

You can then send a POST request to /get with a payload like:
```json
{
  "value": "value to get",
  "tags": ["multi", "value"]
}
```
or
```json
{
  "value": ["values", "to", "get"],
}
```
Where the "tags" field is optional (defaults to all tag types), but if it's specified it should have at least one of the three given values.

### Untagging

Works basically the same as /tag, but with the endpoint /untag instead.

### Searching

Send a POST request to /search with a payload like:
```json
{
  "query": ["tag1", "tag2", "tagN5", "tagN{>5}", "tag%"]
}
```
Where each entry in the list equals one tag to search for.

#### Special syntax

* You can use '%' as a wildcard.
* When searching for value tags, you can use the special syntax: `tag{>5}`, with the available comparators being the same as whatever PostgreSQL version you're using has.

## Setup

Requirements: Docker
Recommended: GNU Make

1. Start the network (make start-network)
2. Start the database (make start-db)
3. Build the tagger (make build-tagger)
4. Start the tagger (make start-tagger)

## Tag types

### Multi tags

Any tag that doesn't fit into value tags

### Value tags

Value tags are for tags that have static names, but variable values ("timestamp:1599902790", "rating:5", etc.). These will be stored as many-to-many relations, with the name of the tag and the value being separate values.  

NOTE: Values will always be found at the end of value tags.

## Cross-hosted
This repository is hosted both on [GitHub](https://github.com/TheNamlessGuy/tmv) and [Codeberg](https://codeberg.org/TheNamlessGuy/tmv).
