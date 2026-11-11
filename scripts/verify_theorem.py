"""Public CLI for the frozen theorem replay and declared field records."""
import sys

if __package__:
    from . import verify_theorem_v1 as _v1
else:
    import verify_theorem_v1 as _v1


def __getattr__(name):
    return getattr(_v1, name)


def main():
    args = sys.argv[1:]
    if args in (["-h"], ["--help"]):
        print("usage: verify_theorem.py {pair,verify-v1,field} ...\n"
              "  pair       compare one fixed direct action with inspection\n"
              "  verify-v1  replay the byte-pinned arithmetic verification\n"
              "  field      compare a declared record: field --input FILE")
        return
    if args[:1] == ["field"]:
        if __package__:
            from . import verify_theorem_field as field
        else:
            import verify_theorem_field as field
        field.main(args[1:])
    else:
        _v1.main()


if __name__ == "__main__":
    main()
