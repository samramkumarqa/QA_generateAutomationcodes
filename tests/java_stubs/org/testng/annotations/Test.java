package org.testng.annotations;
import java.lang.annotation.*;
@Retention(RetentionPolicy.RUNTIME) @Target({ElementType.METHOD, ElementType.TYPE})
public @interface Test { String description() default ""; boolean enabled() default true; }
