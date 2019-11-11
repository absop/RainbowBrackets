(define lwp-list '())

(define lwp
  (lambda (thunk)
    (set! lwp-list (append lwp-list (list thunk)))))

(define start
  (lambda ()
    (let ([p (car lwp-list)])
      (set! lwp-list (cdr lwp-list))
      (p))))

(define pause
  (lambda ()
    (call/cc
      (lambda (k)
        ; (lwp (lambda () (k #f)))
        (lwp k)
        (start)))))

(lwp (lambda () (let f () (display "h") (pause) (f))))
(lwp (lambda () (let f () (display "e") (pause) (f))))
(lwp (lambda () (let f () (display "y") (pause) (f))))
(lwp (lambda () (let f () (display "!") (pause) (f))))
(lwp (lambda () (let f () (newline) (pause) (f))))

(start)
