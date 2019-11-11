(printf "~a\n"
        (apply + (call/cc
                   (lambda (continuation)
                     (continuation '(1 2 3 4 5 6 7))))))

; Emmm continuation <=> 善后
;=> equal to
(printf "~a\n"
        ((lambda (continuation)
           (continuation '(1 2 3 4 5 6 7)))
         (lambda (ls) (apply + ls))))

(printf "~a\n"
        (call/cc
          (lambda (continuation)
            (set! p continuation))))

(printf "~a\n"
        (call/cc
          (lambda (continuation)
            (set! p continuation)
            p)))

(printf "~a\n"
        (call/cc
          (lambda (continuation)
            (set! p continuation)
            "This is a string")))

(printf "~a\n"
        (call/cc
          (lambda (continuation)
            (set! p continuation)
            printf)))
(p p) ;=> #<continuation>

(printf "~a\n"
        (call/cc
          (lambda (continuation)
            (set! p (lambda (x) (continuation x)))
            p)))
;=> #<procedure p at call-cc.ss:728>
;=> equal to (set! p (lambda (x) (printf "~a\n" x)))

(p 1) ;=> 1
(p p) ;=> #<procedure p at call-cc.ss:728>
