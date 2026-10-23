;;; export_mtext_json.lsp
;;; 只导出当前图纸 ModelSpace 中的 MTEXT 到 JSON
;;; 命令：EXPORTMTEXTJSON

(vl-load-com)

(defun json-escape (s / r i ch code)
  (setq r "")
  (setq i 1)

  (while (<= i (strlen s))
    (setq ch (substr s i 1))
    (setq code (ascii ch))

    (cond
      ((= ch "\\") (setq r (strcat r "\\\\")))
      ((= ch "\"") (setq r (strcat r "\\\"")))
      ((= ch "\n") (setq r (strcat r "\\n")))
      ((= ch "\r") (setq r (strcat r "\\r")))
      ((= ch "\t") (setq r (strcat r "\\t")))
      ((< code 32) (setq r r))
      (T (setq r (strcat r ch)))
    )

    (setq i (1+ i))
  )

  r
)


(defun str-replace-all (old new s / pos)
  (while (setq pos (vl-string-search old s))
    (setq s
      (strcat
        (substr s 1 pos)
        new
        (substr s (+ pos (strlen old) 1))
      )
    )
  )
  s
)


(defun clean-mtext (s)
  ;; MTEXT 中 \P 表示换行
  (setq s (str-replace-all "\\P" "\n" s))

  ;; 去除首尾空白
  (vl-string-trim " \t\r\n" s)
)


(defun get-mtext-string (ename / obj s)
  (setq obj (vlax-ename->vla-object ename))
  (setq s (vla-get-TextString obj))

  (if s
    (clean-mtext s)
    ""
  )
)


(defun c:EXPORTMTEXTJSON (/ ss file-path f i ename text count)
  (setq ss (ssget "_X" '((0 . "MTEXT"))))

  (if (not ss)
    (progn
      (princ "\n未找到 MTEXT 对象。")
      (princ)
    )
    (progn
      (setq file-path
        (getfiled
          "导出 MTEXT JSON"
          (strcat (getvar "DWGPREFIX") "cad_mtext.json")
          "json"
          1
        )
      )

      (if file-path
        (progn
          (setq f (open file-path "w"))
          (write-line "[" f)

          (setq i 0)
          (setq count 0)

          (while (< i (sslength ss))
            (setq ename (ssname ss i))
            (setq text (get-mtext-string ename))

            (if (/= text "")
              (progn
                (if (> count 0)
                  (write-line "," f)
                )

                (write-line
                  (strcat "  \"" (json-escape text) "\"")
                  f
                )

                (setq count (1+ count))
              )
            )

            (setq i (1+ i))
          )

          (write-line "" f)
          (write-line "]" f)
          (close f)

          (princ
            (strcat
              "\n完成：导出 "
              (itoa count)
              " 条 MTEXT 到 "
              file-path
            )
          )
        )
        (princ "\n已取消导出。")
      )

      (princ)
    )
  )
)