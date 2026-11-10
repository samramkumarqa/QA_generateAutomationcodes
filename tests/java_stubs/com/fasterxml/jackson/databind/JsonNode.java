package com.fasterxml.jackson.databind;
import java.util.*;
public abstract class JsonNode implements Iterable<JsonNode> { public abstract JsonNode path(String f); public abstract JsonNode get(String f);
  public abstract String asText(); public abstract String asText(String def); public abstract Iterator<Map.Entry<String, JsonNode>> fields(); }
