package org.apache.poi.xssf.usermodel;
import org.apache.poi.ss.usermodel.*; import java.io.*; import java.util.Iterator;
public class XSSFWorkbook implements Workbook { public XSSFWorkbook(InputStream in) throws IOException {}
  public Sheet getSheet(String n){return null;} public void close() throws IOException {} public Iterator<Sheet> iterator(){return null;} }
